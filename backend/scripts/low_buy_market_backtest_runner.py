from __future__ import annotations

from dataclasses import dataclass
import sys
from datetime import date, timedelta
from typing import Callable

import pandas as pd

from app.services.low_buy.execution_simulation import bars_from_repository_rows
from app.services.low_buy.execution_simulation import ExecutionSimulationOverride
from app.services.low_buy_screener import LowBuyScreenerService

try:
    from .low_buy_market_backtest_market_guard import MarketGuardOverride, apply_market_guard
    from .low_buy_market_backtest_candidates import (
        evaluate_candidate_from_metrics,
        iter_snapshot_candidates,
    )
    from .low_buy_market_backtest_outcomes import (
        daily_rows_to_frame,
        evaluate_candidate_outcome,
        evaluate_candidate_outcome_from_bars,
        evaluate_candidate_outcomes_from_bars,
        history_frame_to_date,
    )
    from .low_buy_market_backtest_pools import (
        build_local_hot_context_by_date,
        build_ranked_pools_from_signals,
        fetch_daily_rows_for_backtest,
        fetch_historical_pool_signals,
        load_symbol_metadata,
    )
    from .low_buy_market_backtest_reporting import StrategyBacktestStats, history_window_days
except ImportError:
    from low_buy_market_backtest_market_guard import MarketGuardOverride, apply_market_guard
    from low_buy_market_backtest_candidates import (
        evaluate_candidate_from_metrics,
        iter_snapshot_candidates,
    )
    from low_buy_market_backtest_outcomes import (
        daily_rows_to_frame,
        evaluate_candidate_outcome,
        evaluate_candidate_outcome_from_bars,
        evaluate_candidate_outcomes_from_bars,
        history_frame_to_date,
    )
    from low_buy_market_backtest_pools import (
        build_local_hot_context_by_date,
        build_ranked_pools_from_signals,
        fetch_daily_rows_for_backtest,
        fetch_historical_pool_signals,
        load_symbol_metadata,
    )
    from low_buy_market_backtest_reporting import StrategyBacktestStats, history_window_days


CountSignalStateFn = Callable[[StrategyBacktestStats, str], None]


@dataclass(frozen=True)
class FastBacktestCandidate:
    candidate: object
    market_guard_reason: str = ""


def run_legacy_backtest(
    *,
    db,
    service: LowBuyScreenerService,
    stats: dict[str, StrategyBacktestStats],
    evaluation_dates: list[str],
    latest_completed: str,
    strategy_keys: list[str],
    evaluated_states: set[str],
    execution_override: ExecutionSimulationOverride | None,
    market_guard: MarketGuardOverride | None,
    scan_limit: int,
    limit: int,
    forward_days: int,
    months: int,
    materialization_mode: str,
    load_or_build_snapshot,
    count_signal_state,
) -> None:
    for strategy in strategy_keys:
        for trade_date in evaluation_dates:
            stat = stats[strategy]
            try:
                payload = load_or_build_snapshot(
                    db=db,
                    service=service,
                    strategy=strategy,
                    trade_date=trade_date,
                    limit=limit,
                    scan_limit=scan_limit,
                    materialization_mode=materialization_mode,
                )
            except Exception as exc:
                stat.failed_snapshot_count += 1
                print(f"[backtest] skip {strategy} {trade_date}: {exc}", file=sys.stderr, flush=True)
                db.rollback()
                continue
            if payload is None:
                db.rollback()
                continue
            stat.snapshot_count += 1
            stat.snapshot_dates.add(trade_date)
            stat.scanned_count += payload.scanned_count
            stat.matched_count += payload.matched_count
            for candidate in iter_snapshot_candidates(payload):
                candidate, guard_reason = apply_market_guard(candidate, market_guard)
                if guard_reason:
                    stat.record_market_guard(guard_reason)
                count_signal_state(stat, candidate.buy_signal_state)
                if candidate.buy_signal_state not in evaluated_states:
                    stat.record_skipped_state(candidate.buy_signal_state)
                    continue
                outcome = evaluate_candidate_outcome(
                    service=service,
                    candidate=candidate,
                    signal_date=trade_date,
                    latest_completed=latest_completed,
                    forward_days=forward_days,
                    history_window_days=history_window_days(months, forward_days),
                    execution_override=execution_override,
                )
                if outcome is None:
                    stat.pending_count += 1
                    stat.record_pending_reason("forward_window_incomplete_or_missing_history")
                    continue
                stat.evaluated_count += 1
                stat.outcomes.append(outcome)
            db.rollback()


def run_fast_isolated_backtest(
    *,
    db,
    service: LowBuyScreenerService,
    stats: dict[str, StrategyBacktestStats],
    trade_dates: list[str],
    evaluation_dates: list[str],
    latest_completed: str,
    strategy_keys: list[str],
    evaluated_states: set[str],
    execution_override: ExecutionSimulationOverride | None,
    market_guard: MarketGuardOverride | None,
    scan_limit: int,
    limit: int,
    forward_days: int,
    history_window_days_value: int,
    count_signal_state,
) -> None:
    if not evaluation_dates:
        return
    history_start = (date.fromisoformat(evaluation_dates[0]) - timedelta(days=history_window_days_value)).isoformat()
    symbol_meta = load_symbol_metadata(db)
    signal_by_date = fetch_historical_pool_signals(
        db=db,
        start_date_iso=history_start,
        latest_trade_date=latest_completed,
        trade_dates=trade_dates,
        symbol_meta=symbol_meta,
    )
    ranked_pool_by_date = build_ranked_pools_from_signals(
        signal_by_date=signal_by_date,
        trade_dates=trade_dates,
        evaluation_dates=evaluation_dates,
    )
    pool_symbols = {
        item.symbol
        for ranked_pool in ranked_pool_by_date.values()
        for item in ranked_pool
    }
    rows_by_symbol = fetch_daily_rows_for_backtest(
        db=db,
        symbols=sorted(pool_symbols),
        start_date_iso=history_start,
        latest_trade_date=latest_completed,
    )
    bars_by_symbol: dict[str, list] = {}
    frames_by_symbol: dict[str, pd.DataFrame | None] = {}

    def _frame_for_symbol(symbol: str) -> pd.DataFrame | None:
        if symbol not in frames_by_symbol:
            frames_by_symbol[symbol] = daily_rows_to_frame(rows_by_symbol.get(symbol, []), history_start)
        return frames_by_symbol[symbol]

    def _bars_for_symbol(symbol: str) -> list:
        if symbol not in bars_by_symbol:
            bars_by_symbol[symbol] = bars_from_repository_rows(rows_by_symbol.get(symbol, []))
        return bars_by_symbol[symbol]
    hot_context_by_date = build_local_hot_context_by_date(
        rows_by_symbol=rows_by_symbol,
        trade_dates=trade_dates,
        evaluation_dates=evaluation_dates,
        ranked_pool_by_date=ranked_pool_by_date,
        symbol_meta=symbol_meta,
    )

    total_dates = len(evaluation_dates)
    for date_index, trade_date in enumerate(evaluation_dates, start=1):
        if date_index == 1 or date_index == total_dates or date_index % 10 == 0:
            print(f"[backtest] fast date {date_index}/{total_dates} {trade_date}", flush=True)
        ranked_pool = ranked_pool_by_date.get(trade_date, [])
        if not ranked_pool:
            for strategy in strategy_keys:
                stats[strategy].failed_snapshot_count += 1
            continue
        completed_dates = _completed_dates_to(trade_dates, trade_date)
        scan_targets_by_strategy = {
            strategy: _scan_targets_for_strategy(
                service=service,
                strategy=strategy,
                ranked_pool=ranked_pool,
                completed_dates=completed_dates,
                latest_trade_date=trade_date,
                scan_limit=scan_limit,
            )
            for strategy in strategy_keys
        }
        needed_symbols = {
            item.symbol
            for targets in scan_targets_by_strategy.values()
            for item in targets
        }
        candidate_by_symbol = _candidate_by_symbol(scan_targets_by_strategy)
        histories = {
            symbol: history_frame_to_date(
                _frame_for_symbol(symbol),
                trade_date,
                history_window_days=history_window_days_value,
            )
            for symbol in needed_symbols
        }
        metrics_by_symbol = {
            symbol: metrics
            for symbol, history in histories.items()
            if history is not None
            if (metrics := service._build_candidate_metrics(
                item=candidate_by_symbol[symbol],
                latest_trade_date=trade_date,
                history=history,
            )) is not None
        }
        hot_industries, market_regime = hot_context_by_date.get(trade_date, ([], None))
        for strategy in strategy_keys:
            stat = stats[strategy]
            try:
                _evaluate_fast_strategy_date(
                    service=service,
                    stat=stat,
                    strategy=strategy,
                    trade_date=trade_date,
                    scan_targets=scan_targets_by_strategy[strategy],
                    histories=histories,
                    metrics_by_symbol=metrics_by_symbol,
                    bars_for_symbol=_bars_for_symbol,
                    hot_industries=hot_industries,
                    market_regime=market_regime,
                    limit=limit,
                    forward_days=forward_days,
                    evaluated_states=evaluated_states,
                    execution_override=execution_override,
                    market_guard=market_guard,
                    count_signal_state=count_signal_state,
                )
            except Exception as exc:
                stat.failed_snapshot_count += 1
                print(f"[backtest] fast skip {strategy} {trade_date}: {exc}", file=sys.stderr, flush=True)


def run_fast_isolated_execution_matrix_backtest(
    *,
    db,
    service: LowBuyScreenerService,
    stats_by_variant: dict[str, dict[str, StrategyBacktestStats]],
    trade_dates: list[str],
    evaluation_dates: list[str],
    latest_completed: str,
    strategy_keys: list[str],
    evaluated_states: set[str],
    execution_overrides: dict[str, ExecutionSimulationOverride | None],
    market_guard: MarketGuardOverride | None,
    scan_limit: int,
    limit: int,
    forward_days: int,
    history_window_days_value: int,
    count_signal_state: CountSignalStateFn,
) -> None:
    if not evaluation_dates:
        return
    if not stats_by_variant:
        return
    variant_keys = list(stats_by_variant.keys())
    history_start = (date.fromisoformat(evaluation_dates[0]) - timedelta(days=history_window_days_value)).isoformat()
    symbol_meta = load_symbol_metadata(db)
    signal_by_date = fetch_historical_pool_signals(
        db=db,
        start_date_iso=history_start,
        latest_trade_date=latest_completed,
        trade_dates=trade_dates,
        symbol_meta=symbol_meta,
    )
    ranked_pool_by_date = build_ranked_pools_from_signals(
        signal_by_date=signal_by_date,
        trade_dates=trade_dates,
        evaluation_dates=evaluation_dates,
    )
    pool_symbols = {
        item.symbol
        for ranked_pool in ranked_pool_by_date.values()
        for item in ranked_pool
    }
    rows_by_symbol = fetch_daily_rows_for_backtest(
        db=db,
        symbols=sorted(pool_symbols),
        start_date_iso=history_start,
        latest_trade_date=latest_completed,
    )
    bars_by_symbol: dict[str, list] = {}
    frames_by_symbol: dict[str, pd.DataFrame | None] = {}

    def _frame_for_symbol(symbol: str) -> pd.DataFrame | None:
        if symbol not in frames_by_symbol:
            frames_by_symbol[symbol] = daily_rows_to_frame(rows_by_symbol.get(symbol, []), history_start)
        return frames_by_symbol[symbol]

    def _bars_for_symbol(symbol: str) -> list:
        if symbol not in bars_by_symbol:
            bars_by_symbol[symbol] = bars_from_repository_rows(rows_by_symbol.get(symbol, []))
        return bars_by_symbol[symbol]

    hot_context_by_date = build_local_hot_context_by_date(
        rows_by_symbol=rows_by_symbol,
        trade_dates=trade_dates,
        evaluation_dates=evaluation_dates,
        ranked_pool_by_date=ranked_pool_by_date,
        symbol_meta=symbol_meta,
    )

    total_dates = len(evaluation_dates)
    for date_index, trade_date in enumerate(evaluation_dates, start=1):
        if date_index == 1 or date_index == total_dates or date_index % 10 == 0:
            print(
                f"[backtest] fast matrix date {date_index}/{total_dates} {trade_date} variants={len(variant_keys)}",
                flush=True,
            )
        ranked_pool = ranked_pool_by_date.get(trade_date, [])
        if not ranked_pool:
            for stats in stats_by_variant.values():
                for strategy in strategy_keys:
                    stats[strategy].failed_snapshot_count += 1
            continue
        completed_dates = _completed_dates_to(trade_dates, trade_date)
        scan_targets_by_strategy = {
            strategy: _scan_targets_for_strategy(
                service=service,
                strategy=strategy,
                ranked_pool=ranked_pool,
                completed_dates=completed_dates,
                latest_trade_date=trade_date,
                scan_limit=scan_limit,
            )
            for strategy in strategy_keys
        }
        needed_symbols = {
            item.symbol
            for targets in scan_targets_by_strategy.values()
            for item in targets
        }
        candidate_by_symbol = _candidate_by_symbol(scan_targets_by_strategy)
        histories = {
            symbol: history_frame_to_date(
                _frame_for_symbol(symbol),
                trade_date,
                history_window_days=history_window_days_value,
            )
            for symbol in needed_symbols
        }
        metrics_by_symbol = {
            symbol: metrics
            for symbol, history in histories.items()
            if history is not None
            if (metrics := service._build_candidate_metrics(
                item=candidate_by_symbol[symbol],
                latest_trade_date=trade_date,
                history=history,
            )) is not None
        }
        hot_industries, market_regime = hot_context_by_date.get(trade_date, ([], None))
        for strategy in strategy_keys:
            try:
                base = _evaluate_fast_strategy_date_candidates(
                    service=service,
                    strategy=strategy,
                    trade_date=trade_date,
                    scan_targets=scan_targets_by_strategy[strategy],
                    histories=histories,
                    metrics_by_symbol=metrics_by_symbol,
                    hot_industries=hot_industries,
                    market_regime=market_regime,
                    limit=limit,
                    market_guard=market_guard,
                )
                _record_fast_strategy_candidates_for_matrix(
                    stats_by_variant=stats_by_variant,
                    variant_keys=variant_keys,
                    execution_overrides=execution_overrides,
                    strategy=strategy,
                    trade_date=trade_date,
                    scan_targets_count=len(scan_targets_by_strategy[strategy]),
                    candidates=base,
                    evaluated_states=evaluated_states,
                    bars_for_symbol=_bars_for_symbol,
                    forward_days=forward_days,
                    count_signal_state=count_signal_state,
                )
            except Exception as exc:
                for stats in stats_by_variant.values():
                    stats[strategy].failed_snapshot_count += 1
                print(f"[backtest] fast matrix skip {strategy} {trade_date}: {exc}", file=sys.stderr, flush=True)


def _evaluate_fast_strategy_date(
    *,
    service: LowBuyScreenerService,
    stat: StrategyBacktestStats,
    strategy: str,
    trade_date: str,
    scan_targets: list,
    histories: dict[str, pd.DataFrame | None],
    metrics_by_symbol: dict[str, object],
    bars_for_symbol,
    hot_industries: list[str],
    market_regime,
    limit: int,
    forward_days: int,
    evaluated_states: set[str],
    execution_override: ExecutionSimulationOverride | None,
    market_guard: MarketGuardOverride | None,
    count_signal_state,
) -> None:
    evaluated = _evaluate_fast_strategy_date_candidates(
        service=service,
        strategy=strategy,
        trade_date=trade_date,
        scan_targets=scan_targets,
        histories=histories,
        metrics_by_symbol=metrics_by_symbol,
        hot_industries=hot_industries,
        market_regime=market_regime,
        limit=limit,
        market_guard=market_guard,
    )

    stat.snapshot_count += 1
    stat.snapshot_dates.add(trade_date)
    stat.scanned_count += len(scan_targets)
    stat.matched_count += len(evaluated)
    for item in evaluated:
        candidate = item.candidate
        if item.market_guard_reason:
            stat.record_market_guard(item.market_guard_reason)
        count_signal_state(stat, candidate.buy_signal_state)
        if candidate.buy_signal_state not in evaluated_states:
            stat.record_skipped_state(candidate.buy_signal_state)
            continue
        outcome = evaluate_candidate_outcome_from_bars(
            candidate=candidate,
            signal_date=trade_date,
            bars=bars_for_symbol(candidate.symbol),
            forward_days=forward_days,
            execution_override=execution_override,
        )
        if outcome is None:
            stat.pending_count += 1
            stat.record_pending_reason("forward_window_incomplete_or_missing_bars")
            continue
        stat.evaluated_count += 1
        stat.outcomes.append(outcome)


def _evaluate_fast_strategy_date_candidates(
    *,
    service: LowBuyScreenerService,
    strategy: str,
    trade_date: str,
    scan_targets: list,
    histories: dict[str, pd.DataFrame | None],
    metrics_by_symbol: dict[str, object],
    hot_industries: list[str],
    market_regime,
    limit: int,
    market_guard: MarketGuardOverride | None,
) -> list[FastBacktestCandidate]:
    evaluated = []
    for item in scan_targets:
        history = histories.get(item.symbol)
        metrics = metrics_by_symbol.get(item.symbol)
        if metrics is None:
            continue
        candidate = evaluate_candidate_from_metrics(
            service=service,
            item=item,
            latest_trade_date=trade_date,
            strategy=strategy,
            hot_industries=hot_industries,
            market_regime=market_regime,
            metrics=metrics,
        )
        if candidate is None or history is None or history.empty:
            continue
        latest_rows = history.index[history["date"] == trade_date].tolist()
        if latest_rows:
            refreshed = service._refresh_historical_buy_signal(candidate, history.iloc[latest_rows[-1]])
            refreshed, guard_reason = apply_market_guard(refreshed, market_guard)
            evaluated.append(FastBacktestCandidate(candidate=refreshed, market_guard_reason=guard_reason))
    deduped = _dedupe_fast_backtest_candidates(service, evaluated)
    deduped.sort(key=lambda item: (service._signal_rank(item.candidate.buy_signal_state), item.candidate.score), reverse=True)
    confirmed_candidates = [
        item for item in deduped if item.candidate.buy_signal_state in service._confirmed_signal_states
    ][:12]
    candidates = [
        item for item in deduped if item.candidate.buy_signal_state not in service._confirmed_signal_states
    ][:limit]
    return confirmed_candidates + candidates


def _record_fast_strategy_candidates_for_matrix(
    *,
    stats_by_variant: dict[str, dict[str, StrategyBacktestStats]],
    variant_keys: list[str],
    execution_overrides: dict[str, ExecutionSimulationOverride | None],
    strategy: str,
    trade_date: str,
    scan_targets_count: int,
    candidates: list[FastBacktestCandidate],
    evaluated_states: set[str],
    bars_for_symbol,
    forward_days: int,
    count_signal_state: CountSignalStateFn,
) -> None:
    for variant_key in variant_keys:
        stat = stats_by_variant[variant_key][strategy]
        stat.snapshot_count += 1
        stat.snapshot_dates.add(trade_date)
        stat.scanned_count += scan_targets_count
        stat.matched_count += len(candidates)

    candidate_outcome_cache: dict[tuple[str, str], dict[str, object] | None] = {}
    for item in candidates:
        candidate = item.candidate
        guard_reason = item.market_guard_reason
        outcome_map: dict[str, object] | None = None
        for variant_key in variant_keys:
            stat = stats_by_variant[variant_key][strategy]
            if guard_reason:
                stat.record_market_guard(guard_reason)
            count_signal_state(stat, candidate.buy_signal_state)
            if candidate.buy_signal_state not in evaluated_states:
                stat.record_skipped_state(candidate.buy_signal_state)
                continue
            cache_key = (candidate.strategy_key, candidate.symbol)
            if outcome_map is None and cache_key not in candidate_outcome_cache:
                candidate_outcome_cache[cache_key] = evaluate_candidate_outcomes_from_bars(
                    candidate=candidate,
                    signal_date=trade_date,
                    bars=bars_for_symbol(candidate.symbol),
                    forward_days=forward_days,
                    execution_overrides=execution_overrides,
                )
            outcome_map = candidate_outcome_cache.get(cache_key)
            outcome = outcome_map.get(variant_key) if outcome_map else None
            if outcome is None:
                stat.pending_count += 1
                stat.record_pending_reason("forward_window_incomplete_or_missing_bars")
                continue
            stat.evaluated_count += 1
            stat.outcomes.append(outcome)


def _dedupe_fast_backtest_candidates(
    service: LowBuyScreenerService,
    candidates: list[FastBacktestCandidate],
) -> list[FastBacktestCandidate]:
    if not candidates:
        return []
    best_by_key: dict[str, FastBacktestCandidate] = {}
    for item in candidates:
        candidate = item.candidate
        key = candidate.symbol
        existing = best_by_key.get(key)
        if existing is None or (
            service._signal_rank(candidate.buy_signal_state),
            candidate.score,
        ) >= (
            service._signal_rank(existing.candidate.buy_signal_state),
            existing.candidate.score,
        ):
            best_by_key[key] = item
    return list(best_by_key.values())


def _scan_targets_for_strategy(
    *,
    service: LowBuyScreenerService,
    strategy: str,
    ranked_pool: list,
    completed_dates: list[str],
    latest_trade_date: str,
    scan_limit: int,
) -> list:
    retracement_buckets = service._build_retracement_buckets(
        ranked_pool=ranked_pool,
        completed_trade_dates=completed_dates,
        latest_trade_date=latest_trade_date,
        max_days=service._strategy_retracement_days_max(strategy),
    )
    eligible_targets = [item for bucket in retracement_buckets.values() for item in bucket]
    return eligible_targets if scan_limit <= 0 else eligible_targets[:scan_limit]


def _completed_dates_to(trade_dates: list[str], trade_date: str) -> list[str]:
    try:
        index = trade_dates.index(trade_date)
    except ValueError:
        return [item for item in trade_dates if item <= trade_date]
    return trade_dates[: index + 1]


def _candidate_by_symbol(scan_targets_by_strategy: dict[str, list]) -> dict[str, object]:
    candidates: dict[str, object] = {}
    for targets in scan_targets_by_strategy.values():
        for item in targets:
            candidates.setdefault(item.symbol, item)
    return candidates
