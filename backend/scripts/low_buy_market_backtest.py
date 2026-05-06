from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median
from typing import Any

import pandas as pd
from sqlalchemy import and_, or_, select

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "backend"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.core.database import SessionLocal, init_db
from app.models.entities import DailyBarSnapshot, Instrument, LowBuyPoolSnapshot
from app.models.schemas import LowBuyCandidateOut
from app.repositories.low_buy import DailyHistoryRepository
from app.services.market.emotion import MarketEmotionSnapshot
from app.services.market.regime_scoring import classify_market_regime
from app.services.market.regime_types import MarketBreadthSnapshot
from app.services.low_buy_screener import PLAYBOOKS, LowBuyScreenerService
from app.services.low_buy.candidate_metrics import passes_common_prefilter
from app.services.low_buy.candidate_rules import build_strategy_setup, passes_strategy_prefilter, score_candidate
from app.services.low_buy.data_quality import build_low_buy_metrics_quality
from app.services.low_buy.execution_simulation import bars_from_history_frame, bars_from_repository_rows, simulate_candidate_execution
from app.services.low_buy.signal_family import build_signal_family_profile, profile_with_setup
from app.services.low_buy.shared import PERFORMANCE_FORWARD_DAYS, BoardCandidate
from app.services.low_buy.strategy_families import resolve_strategy_family, resolve_strategy_family_label


CONFIRMED_STATES = {"buy_now", "soft_buy_now"}
NEAR_ENTRY_STATE = "near_entry"
EVALUATED_STATES = CONFIRMED_STATES | {NEAR_ENTRY_STATE}
SIGNAL_GROUPS = {
    "confirmed": ("确定买入", CONFIRMED_STATES),
    "near_entry": ("接近买点", {NEAR_ENTRY_STATE}),
}


@dataclass
class TradeOutcome:
    symbol: str
    name: str
    signal_date: str
    strategy_key: str
    buy_signal_state: str
    entry_price: float
    execution_status: str
    net_return_pct: float
    execution_exit_reason: str
    return_1d: float
    return_2d: float
    return_3d: float
    return_4d: float
    return_5d: float
    max_gain_5d: float
    max_drawdown_5d: float
    t1_high_return_pct: float = 0.0
    t1_close_return_pct: float = 0.0
    t1_spike_fade_pct: float = 0.0
    t2_high_return_pct: float = 0.0
    t2_close_return_pct: float = 0.0
    t1_hit_3_pct: bool = False
    t1_hit_5_pct: bool = False
    t1_fade_to_entry: bool = False


@dataclass
class StrategyBacktestStats:
    strategy_key: str
    strategy_title: str
    strategy_family: str
    strategy_family_text: str
    snapshot_count: int = 0
    snapshot_dates: set[str] = field(default_factory=set)
    failed_snapshot_count: int = 0
    scanned_count: int = 0
    matched_count: int = 0
    confirmed_count: int = 0
    near_entry_count: int = 0
    watch_count: int = 0
    avoid_count: int = 0
    evaluated_count: int = 0
    pending_count: int = 0
    outcomes: list[TradeOutcome] = field(default_factory=list)

    def as_dict(self, target_profit_pct: float) -> dict[str, Any]:
        confirmed_result = _signal_group_stats(
            outcomes=self.outcomes,
            states=CONFIRMED_STATES,
            target_profit_pct=target_profit_pct,
        )
        near_entry_result = _signal_group_stats(
            outcomes=self.outcomes,
            states={NEAR_ENTRY_STATE},
            target_profit_pct=target_profit_pct,
        )
        total_result = _signal_group_stats(
            outcomes=self.outcomes,
            states=EVALUATED_STATES,
            target_profit_pct=target_profit_pct,
        )
        return {
            "strategy_key": self.strategy_key,
            "strategy_title": self.strategy_title,
            "strategy_family": self.strategy_family,
            "strategy_family_text": self.strategy_family_text,
            "snapshot_count": self.snapshot_count,
            "snapshot_start": min(self.snapshot_dates) if self.snapshot_dates else "",
            "snapshot_end": max(self.snapshot_dates) if self.snapshot_dates else "",
            "failed_snapshot_count": self.failed_snapshot_count,
            "scanned_count": self.scanned_count,
            "matched_count": self.matched_count,
            "confirmed_count": self.confirmed_count,
            "near_entry_count": self.near_entry_count,
            "watch_count": self.watch_count,
            "avoid_count": self.avoid_count,
            "evaluated_count": self.evaluated_count,
            "pending_count": self.pending_count,
            "confirmed_result": confirmed_result,
            "near_entry_result": near_entry_result,
            "total_evaluated_result": total_result,
            "hit_count": confirmed_result["hit_count"],
            "hit_rate": confirmed_result["hit_rate"],
            "win_rate_1d": confirmed_result["win_rate_1d"],
            "win_rate_2d": confirmed_result["win_rate_2d"],
            "win_rate_3d": confirmed_result["win_rate_3d"],
            "win_rate_4d": confirmed_result["win_rate_4d"],
            "win_rate_5d": confirmed_result["win_rate_5d"],
            "avg_return_1d": confirmed_result["avg_return_1d"],
            "avg_return_2d": confirmed_result["avg_return_2d"],
            "avg_return_3d": confirmed_result["avg_return_3d"],
            "avg_return_4d": confirmed_result["avg_return_4d"],
            "avg_return_5d": confirmed_result["avg_return_5d"],
            "median_return_5d": confirmed_result["median_return_5d"],
            "avg_max_gain_5d": confirmed_result["avg_max_gain_5d"],
            "avg_max_drawdown_5d": confirmed_result["avg_max_drawdown_5d"],
            "profit_factor_5d": confirmed_result["profit_factor_5d"],
            "sample_quality": _sample_quality(self.evaluated_count),
            "conclusion": _strategy_conclusion(
                evaluated_count=confirmed_result["evaluated_count"],
                hit_rate=confirmed_result["net_win_rate"],
                avg_return_5d=confirmed_result["avg_net_return_pct"],
                avg_max_drawdown_5d=confirmed_result["avg_max_drawdown_5d"],
            ),
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="低吸策略 A 股全市场回测")
    parser.add_argument("--months", type=int, default=3, help="回测月份数，默认 3")
    parser.add_argument("--scan-limit", type=int, default=480, help="每个交易日最大扫描样本")
    parser.add_argument("--limit", type=int, default=80, help="每个策略每天保留的候选数量")
    parser.add_argument("--target-profit-pct", type=float, default=3.0, help="5 日内命中目标涨幅")
    parser.add_argument("--forward-days", type=int, default=PERFORMANCE_FORWARD_DAYS, help="向后评估交易日数量")
    parser.add_argument("--strategies", default="all", help="逗号分隔策略 key，默认 all")
    parser.add_argument("--max-dates", type=int, default=0, help="调试用，只跑最近 N 个评估交易日")
    parser.add_argument(
        "--engine",
        choices=("fast", "legacy"),
        default="fast",
        help="fast=批量预加载候选池和日线；legacy=沿用旧的逐日逐策略回放。",
    )
    parser.add_argument(
        "--materialization-mode",
        choices=("isolated", "production", "read-only"),
        default="isolated",
        help="回测快照来源。isolated=隔离计算不写生产表；production=写入生产物化表；read-only=只读已有物化表。",
    )
    parser.add_argument("--no-materialize", action="store_true", help="兼容旧参数，等价于 --materialization-mode read-only")
    parser.add_argument("--output-dir", default=str(APP_DIR / "data" / "reports"), help="报告输出目录")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    materialization_mode = "read-only" if args.no_materialize else args.materialization_mode
    init_db()
    service = LowBuyScreenerService()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with SessionLocal() as db:
        trade_dates = service._get_recent_trade_dates(max(160, args.months * 31 + args.forward_days + 50))
        latest_completed = service._resolve_latest_completed_trade_date(trade_dates)
        evaluation_dates = _evaluation_dates(
            trade_dates=trade_dates,
            latest_completed=latest_completed,
            months=args.months,
            forward_days=args.forward_days,
        )
        if args.max_dates > 0:
            evaluation_dates = evaluation_dates[-args.max_dates :]
        strategy_keys = _resolve_strategy_keys(args.strategies)
        universe_count = _load_a_share_universe_count(db, service)
        stats = {
            strategy: StrategyBacktestStats(
                strategy_key=strategy,
                strategy_title=PLAYBOOKS[strategy]["title"],
                strategy_family=resolve_strategy_family(strategy),
                strategy_family_text=resolve_strategy_family_label(strategy),
            )
            for strategy in strategy_keys
        }

        if args.engine == "fast" and materialization_mode == "isolated":
            _run_fast_isolated_backtest(
                db=db,
                service=service,
                stats=stats,
                trade_dates=trade_dates,
                evaluation_dates=evaluation_dates,
                latest_completed=latest_completed,
                strategy_keys=strategy_keys,
                scan_limit=args.scan_limit,
                limit=args.limit,
                forward_days=args.forward_days,
                history_window_days=_history_window_days(args.months, args.forward_days),
            )
        else:
            _run_legacy_backtest(
                db=db,
                service=service,
                stats=stats,
                evaluation_dates=evaluation_dates,
                latest_completed=latest_completed,
                strategy_keys=strategy_keys,
                scan_limit=args.scan_limit,
                limit=args.limit,
                forward_days=args.forward_days,
                months=args.months,
                materialization_mode=materialization_mode,
            )

        report = _build_report(
            universe_count=universe_count,
            latest_completed=latest_completed,
            evaluation_dates=evaluation_dates,
            target_profit_pct=args.target_profit_pct,
            scan_limit=args.scan_limit,
            months=args.months,
            materialization_mode=f"{materialization_mode}/{args.engine}",
            stats=list(stats.values()),
        )

    stem = (
        f"low_buy_market_backtest_{args.months}m_{evaluation_dates[0]}_{evaluation_dates[-1]}"
        if evaluation_dates
        else f"low_buy_market_backtest_{args.months}m_empty"
    )
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown_report(report), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 0


def _run_legacy_backtest(
    *,
    db,
    service: LowBuyScreenerService,
    stats: dict[str, StrategyBacktestStats],
    evaluation_dates: list[str],
    latest_completed: str,
    strategy_keys: list[str],
    scan_limit: int,
    limit: int,
    forward_days: int,
    months: int,
    materialization_mode: str,
) -> None:
    for strategy in strategy_keys:
        for trade_date in evaluation_dates:
            stat = stats[strategy]
            try:
                payload = _load_or_build_snapshot(
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
            for candidate in _iter_snapshot_candidates(payload):
                _count_signal_state(stat, candidate.buy_signal_state)
                if candidate.buy_signal_state not in EVALUATED_STATES:
                    continue
                outcome = _evaluate_candidate_outcome(
                    service=service,
                    candidate=candidate,
                    signal_date=trade_date,
                    latest_completed=latest_completed,
                    forward_days=forward_days,
                    history_window_days=_history_window_days(months, forward_days),
                )
                if outcome is None:
                    stat.pending_count += 1
                    continue
                stat.evaluated_count += 1
                stat.outcomes.append(outcome)
            db.rollback()


def _run_fast_isolated_backtest(
    *,
    db,
    service: LowBuyScreenerService,
    stats: dict[str, StrategyBacktestStats],
    trade_dates: list[str],
    evaluation_dates: list[str],
    latest_completed: str,
    strategy_keys: list[str],
    scan_limit: int,
    limit: int,
    forward_days: int,
    history_window_days: int,
) -> None:
    if not evaluation_dates:
        return
    history_start = (date.fromisoformat(evaluation_dates[0]) - timedelta(days=history_window_days)).isoformat()
    symbol_meta = _load_symbol_metadata(db)
    signal_by_date = _fetch_historical_pool_signals(
        db=db,
        start_date_iso=history_start,
        latest_trade_date=latest_completed,
        trade_dates=trade_dates,
        symbol_meta=symbol_meta,
    )
    ranked_pool_by_date = _build_ranked_pools_from_signals(
        signal_by_date=signal_by_date,
        trade_dates=trade_dates,
        evaluation_dates=evaluation_dates,
    )
    pool_symbols = {
        item.symbol
        for ranked_pool in ranked_pool_by_date.values()
        for item in ranked_pool
    }
    rows_by_symbol = _fetch_daily_rows_for_backtest(
        db=db,
        symbols=sorted(pool_symbols),
        start_date_iso=history_start,
        latest_trade_date=latest_completed,
    )
    bars_by_symbol = {
        symbol: bars_from_repository_rows(rows)
        for symbol, rows in rows_by_symbol.items()
    }
    frames_by_symbol = {
        symbol: _daily_rows_to_frame(rows, history_start)
        for symbol, rows in rows_by_symbol.items()
    }
    hot_context_by_date = _build_local_hot_context_by_date(
        rows_by_symbol=rows_by_symbol,
        trade_dates=trade_dates,
        evaluation_dates=evaluation_dates,
        ranked_pool_by_date=ranked_pool_by_date,
        symbol_meta=symbol_meta,
    )

    total_dates = len(evaluation_dates)
    for date_index, trade_date in enumerate(evaluation_dates, start=1):
        if date_index == 1 or date_index == total_dates or date_index % 20 == 0:
            print(f"[backtest] fast date {date_index}/{total_dates} {trade_date}", flush=True)
        ranked_pool = ranked_pool_by_date.get(trade_date, [])
        if not ranked_pool:
            for strategy in strategy_keys:
                stats[strategy].failed_snapshot_count += 1
            continue
        histories = {
            item.symbol: _history_frame_to_date(
                frames_by_symbol.get(item.symbol),
                trade_date,
                history_window_days=history_window_days,
            )
            for item in ranked_pool
        }
        metrics_by_symbol = {
            item.symbol: metrics
            for item in ranked_pool
            if (metrics := service._build_candidate_metrics(
                item=item,
                latest_trade_date=trade_date,
                history=histories.get(item.symbol),
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
                    trade_dates=trade_dates,
                    trade_date=trade_date,
                    ranked_pool=ranked_pool,
                    histories=histories,
                    metrics_by_symbol=metrics_by_symbol,
                    bars_by_symbol=bars_by_symbol,
                    latest_completed=latest_completed,
                    hot_industries=hot_industries,
                    market_regime=market_regime,
                    scan_limit=scan_limit,
                    limit=limit,
                    forward_days=forward_days,
                )
            except Exception as exc:
                stat.failed_snapshot_count += 1
                print(f"[backtest] fast skip {strategy} {trade_date}: {exc}", file=sys.stderr, flush=True)


def _load_daily_history_symbols(
    *,
    db,
    start_date_iso: str,
    latest_trade_date: str,
) -> list[str]:
    rows = db.execute(
        select(DailyBarSnapshot.symbol)
        .where(
            DailyBarSnapshot.trade_date >= start_date_iso,
            DailyBarSnapshot.trade_date <= latest_trade_date,
        )
        .distinct()
        .order_by(DailyBarSnapshot.symbol.asc())
    ).all()
    return [str(row[0]) for row in rows if _is_stock_symbol(str(row[0]))]


def _fetch_daily_rows_for_backtest(
    *,
    db,
    symbols: list[str],
    start_date_iso: str,
    latest_trade_date: str,
    chunk_size: int = 320,
) -> dict[str, list]:
    repository = DailyHistoryRepository(db)
    rows_by_symbol: dict[str, list] = {}
    for chunk in _chunked(symbols, chunk_size):
        rows_by_symbol.update(
            repository.fetch_rows_for_symbols(
                symbols=chunk,
                start_date_iso=start_date_iso,
                latest_trade_date=latest_trade_date,
            )
        )
    return rows_by_symbol


def _load_symbol_metadata(db) -> dict[str, tuple[str, str]]:
    metadata: dict[str, tuple[str, str]] = {}
    instrument_rows = db.execute(
        select(Instrument.symbol, Instrument.name).where(Instrument.instrument_type == "stock")
    ).all()
    for symbol, name in instrument_rows:
        cleaned_symbol = str(symbol)
        metadata[cleaned_symbol] = (str(name or cleaned_symbol), "")

    pool_rows = db.execute(
        select(LowBuyPoolSnapshot.symbol, LowBuyPoolSnapshot.name, LowBuyPoolSnapshot.industry)
        .where(LowBuyPoolSnapshot.industry != "")
    ).all()
    for symbol, name, industry in pool_rows:
        cleaned_symbol = str(symbol)
        current_name, current_industry = metadata.get(cleaned_symbol, (str(name or cleaned_symbol), ""))
        metadata[cleaned_symbol] = (
            current_name if current_name != cleaned_symbol else str(name or cleaned_symbol),
            str(industry or current_industry or ""),
        )

    return metadata


def _fetch_historical_pool_signals(
    *,
    db,
    start_date_iso: str,
    latest_trade_date: str,
    trade_dates: list[str],
    symbol_meta: dict[str, tuple[str, str]],
) -> dict[str, list[BoardCandidate]]:
    rows = db.execute(
        select(
            DailyBarSnapshot.symbol,
            DailyBarSnapshot.trade_date,
            DailyBarSnapshot.open_price,
            DailyBarSnapshot.close_price,
            DailyBarSnapshot.high_price,
            DailyBarSnapshot.amount,
            DailyBarSnapshot.pct_chg,
        )
        .where(
            DailyBarSnapshot.trade_date >= start_date_iso,
            DailyBarSnapshot.trade_date <= latest_trade_date,
            or_(
                DailyBarSnapshot.pct_chg >= 9.2,
                and_(
                    DailyBarSnapshot.pct_chg >= 8.2,
                    DailyBarSnapshot.close_price >= DailyBarSnapshot.open_price * 1.06,
                    DailyBarSnapshot.close_price >= DailyBarSnapshot.high_price * 0.985,
                    DailyBarSnapshot.amount >= 80_000_000,
                ),
            ),
        )
        .order_by(DailyBarSnapshot.symbol.asc(), DailyBarSnapshot.trade_date.asc())
    ).all()
    trade_index = {trade_date: index for index, trade_date in enumerate(trade_dates)}
    last_limit_index_by_symbol: dict[str, int] = {}
    board_count_by_symbol: dict[str, int] = {}
    signal_by_date: dict[str, list[BoardCandidate]] = {}
    for symbol, trade_date, open_price, close_price, high_price, amount, pct_chg in rows:
        symbol = str(symbol)
        name, industry = symbol_meta.get(symbol, (symbol, ""))
        if _is_backtest_excluded_symbol(symbol, name):
            continue
        open_value = float(open_price or 0.0)
        close_value = float(close_price or 0.0)
        high_value = float(high_price or 0.0)
        amount_value = float(amount or 0.0)
        pct_value = float(pct_chg or 0.0)
        limit_like = pct_value >= 9.2
        strong_like = (
            pct_value >= 8.2
            and open_value > 0
            and high_value > 0
            and close_value >= open_value * 1.06
            and close_value >= high_value * 0.985
            and amount_value >= 80_000_000
        )
        if not limit_like and not strong_like:
            continue
        current_index = trade_index.get(str(trade_date), -10_000)
        previous_limit_index = last_limit_index_by_symbol.get(symbol)
        if limit_like and previous_limit_index == current_index - 1:
            board_count_by_symbol[symbol] = board_count_by_symbol.get(symbol, 1) + 1
        elif limit_like:
            board_count_by_symbol[symbol] = 1
        signal_by_date.setdefault(str(trade_date), []).append(
            BoardCandidate(
                symbol=symbol,
                name=name or symbol,
                board_date=str(trade_date),
                board_count=max(board_count_by_symbol.get(symbol, 1), 1),
                amount=amount_value,
                industry=industry,
            )
        )
        if limit_like:
            last_limit_index_by_symbol[symbol] = current_index
    return signal_by_date


def _build_ranked_pools_from_signals(
    *,
    signal_by_date: dict[str, list[BoardCandidate]],
    trade_dates: list[str],
    evaluation_dates: list[str],
) -> dict[str, list[BoardCandidate]]:
    trade_date_index = {trade_date: index for index, trade_date in enumerate(trade_dates)}
    pools: dict[str, list[BoardCandidate]] = {}
    for trade_date in evaluation_dates:
        latest_index = trade_date_index.get(trade_date)
        if latest_index is None:
            pools[trade_date] = []
            continue
        board_window = trade_dates[max(0, latest_index - 13) : latest_index + 1]
        pooled: dict[str, BoardCandidate] = {}
        for board_date in board_window:
            if board_date >= trade_date:
                continue
            for item in signal_by_date.get(board_date, []):
                current = pooled.get(item.symbol)
                if current is None or current.board_date < item.board_date:
                    pooled[item.symbol] = item
        pools[trade_date] = sorted(
            pooled.values(),
            key=lambda item: (item.board_date, item.board_count == 1, item.amount),
            reverse=True,
        )
    return pools


def _build_ranked_pools_from_daily_rows(
    *,
    rows_by_symbol: dict[str, list],
    trade_dates: list[str],
    evaluation_dates: list[str],
    symbol_meta: dict[str, tuple[str, str]],
) -> dict[str, list[BoardCandidate]]:
    signal_by_date = _collect_historical_pool_signals(
        rows_by_symbol=rows_by_symbol,
        symbol_meta=symbol_meta,
    )
    trade_date_index = {trade_date: index for index, trade_date in enumerate(trade_dates)}
    pools: dict[str, list[BoardCandidate]] = {}
    for trade_date in evaluation_dates:
        latest_index = trade_date_index.get(trade_date)
        if latest_index is None:
            pools[trade_date] = []
            continue
        board_window = trade_dates[max(0, latest_index - 13) : latest_index + 1]
        pooled: dict[str, BoardCandidate] = {}
        for board_date in board_window:
            if board_date >= trade_date:
                continue
            for item in signal_by_date.get(board_date, []):
                current = pooled.get(item.symbol)
                if current is None or current.board_date < item.board_date:
                    pooled[item.symbol] = item
        pools[trade_date] = sorted(
            pooled.values(),
            key=lambda item: (item.board_date, item.board_count == 1, item.amount),
            reverse=True,
        )
    return pools


def _collect_historical_pool_signals(
    *,
    rows_by_symbol: dict[str, list],
    symbol_meta: dict[str, tuple[str, str]],
) -> dict[str, list[BoardCandidate]]:
    signal_by_date: dict[str, list[BoardCandidate]] = {}
    for symbol, rows in rows_by_symbol.items():
        name, industry = symbol_meta.get(symbol, (symbol, ""))
        if _is_backtest_excluded_symbol(symbol, name):
            continue
        consecutive_boards = 0
        previous_close = 0.0
        for row in rows:
            limit_like = _is_limit_like_bar(row=row, previous_close=previous_close)
            strong_like = _is_strong_launch_bar(row=row)
            if limit_like:
                consecutive_boards += 1
            else:
                consecutive_boards = 0
            if limit_like or strong_like:
                signal_by_date.setdefault(row.trade_date, []).append(
                    BoardCandidate(
                        symbol=symbol,
                        name=name or symbol,
                        board_date=row.trade_date,
                        board_count=max(consecutive_boards, 1),
                        amount=float(row.amount or 0.0),
                        industry=industry,
                    )
                )
            previous_close = float(row.close_price or previous_close or 0.0)
    return signal_by_date


def _is_limit_like_bar(*, row, previous_close: float) -> bool:
    close_price = float(row.close_price or 0.0)
    high_price = float(row.high_price or 0.0)
    pct_chg = float(row.pct_chg or 0.0)
    if pct_chg >= 9.2:
        return True
    if previous_close <= 0:
        return False
    return high_price >= previous_close * 1.095 and close_price >= previous_close * 1.085


def _is_strong_launch_bar(row) -> bool:
    open_price = float(row.open_price or 0.0)
    close_price = float(row.close_price or 0.0)
    high_price = float(row.high_price or 0.0)
    amount = float(row.amount or 0.0)
    pct_chg = float(row.pct_chg or 0.0)
    if min(open_price, close_price, high_price) <= 0:
        return False
    return (
        pct_chg >= 8.2
        and close_price >= open_price * 1.06
        and close_price >= high_price * 0.985
        and amount >= 80_000_000
    )


def _is_stock_symbol(symbol: str) -> bool:
    return len(symbol) == 6 and symbol.isdigit() and not symbol.startswith(("1", "4", "5", "8", "68"))


def _is_backtest_excluded_symbol(symbol: str, name: str) -> bool:
    return not _is_stock_symbol(symbol) or "ST" in name.upper()


def _chunked(items: list[str], chunk_size: int):
    for index in range(0, len(items), max(chunk_size, 1)):
        yield items[index : index + chunk_size]


def _load_ranked_pools_by_date(
    *,
    db,
    service: LowBuyScreenerService,
    trade_dates: list[str],
    evaluation_dates: list[str],
) -> dict[str, list]:
    trade_date_set = set(trade_dates)
    pools: dict[str, list] = {}
    for trade_date in evaluation_dates:
        if trade_date not in trade_date_set:
            pools[trade_date] = []
            continue
        completed = [item for item in trade_dates if item <= trade_date]
        board_dates = completed[-13:]
        pools[trade_date] = service._load_ranked_pool(
            db=db,
            latest_trade_date=trade_date,
            board_dates=board_dates,
        )
    return pools


def _build_local_hot_context_by_date(
    *,
    rows_by_symbol: dict[str, list],
    trade_dates: list[str],
    evaluation_dates: list[str],
    ranked_pool_by_date: dict[str, list],
    symbol_meta: dict[str, tuple[str, str]],
) -> dict[str, tuple[list[str], object]]:
    rows_by_date = _index_daily_rows_by_date(rows_by_symbol)
    signal_by_date = _collect_historical_pool_signals(
        rows_by_symbol=rows_by_symbol,
        symbol_meta=symbol_meta,
    )
    contexts: dict[str, tuple[list[str], object]] = {}
    previous_hot_industries: list[str] = []
    previous_limit_up_count = 0
    previous_board_height = 0
    for trade_date in trade_dates:
        if trade_date not in evaluation_dates:
            previous_hot_industries = _top_hot_industries(ranked_pool_by_date.get(trade_date, [])) or previous_hot_industries
            previous_limit_up_count, previous_board_height = _emotion_counts(signal_by_date.get(trade_date, []))
            continue

        hot_industries = _top_hot_industries(ranked_pool_by_date.get(trade_date, []))
        hot_overlap = _hot_overlap_ratio(hot_industries, previous_hot_industries)
        hot_turnover = round(max(0.0, 1.0 - hot_overlap), 4)
        board_frame = _build_local_board_frame(
            rows=rows_by_date.get(trade_date, []),
            symbol_meta=symbol_meta,
        )
        breadth = _build_local_breadth_snapshot(
            rows_by_date.get(trade_date, []),
            hot_turnover=hot_turnover,
            hot_overlap_ratio=hot_overlap,
        )
        current_signals = signal_by_date.get(trade_date, [])
        limit_up_count, board_height = _emotion_counts(current_signals)
        emotion = _build_local_emotion_snapshot(
            limit_up_count=limit_up_count,
            previous_limit_up_count=previous_limit_up_count,
            board_height=board_height,
            previous_board_height=previous_board_height,
            hot_turnover=hot_turnover,
        )
        regime = classify_market_regime(
            board_frame,
            limit_down_count=_limit_down_count(rows_by_date.get(trade_date, [])),
            hot_industries=hot_industries,
            hot_industry_source="local_daily_history",
            hot_industry_source_text="本地日线历史推导",
            breadth_snapshot=breadth,
            emotion_snapshot=emotion,
        )
        contexts[trade_date] = (hot_industries, regime)
        previous_hot_industries = hot_industries or previous_hot_industries
        previous_limit_up_count = limit_up_count
        previous_board_height = board_height
    return contexts


def _index_daily_rows_by_date(rows_by_symbol: dict[str, list]) -> dict[str, list]:
    rows_by_date: dict[str, list] = defaultdict(list)
    for symbol, rows in rows_by_symbol.items():
        for row in rows:
            rows_by_date[row.trade_date].append((symbol, row))
    return rows_by_date


def _top_hot_industries(ranked_pool: list, limit: int = 5) -> list[str]:
    scores: Counter[str] = Counter()
    for item in ranked_pool:
        industry = str(getattr(item, "industry", "") or "").strip()
        if not industry:
            continue
        scores[industry] += max(float(getattr(item, "amount", 0.0) or 0.0), 1.0)
    return [industry for industry, _ in scores.most_common(limit)]


def _build_local_board_frame(*, rows: list, symbol_meta: dict[str, tuple[str, str]]) -> pd.DataFrame | None:
    industry_changes: dict[str, list[float]] = defaultdict(list)
    for symbol, row in rows:
        _, industry = symbol_meta.get(str(symbol), ("", ""))
        if not industry:
            continue
        industry_changes[industry].append(float(row.pct_chg or 0.0))
    if not industry_changes:
        return None
    frame = pd.DataFrame(
        [
            {"industry": industry, "change_pct": mean(changes)}
            for industry, changes in industry_changes.items()
            if changes
        ]
    )
    if frame.empty:
        return None
    return frame.sort_values("change_pct", ascending=False).reset_index(drop=True)


def _build_local_breadth_snapshot(rows: list, *, hot_turnover: float, hot_overlap_ratio: float) -> MarketBreadthSnapshot:
    if not rows:
        return MarketBreadthSnapshot(
            breadth_ready=False,
            stock_up_ratio=0.0,
            stock_median_change=0.0,
            largecap_change=0.0,
            smallcap_change=0.0,
            style_divergence=0.0,
            hot_turnover=hot_turnover,
            hot_overlap_ratio=hot_overlap_ratio,
        )
    changes = [float(row.pct_chg or 0.0) for _, row in rows]
    ordered_by_amount = sorted((row for _, row in rows), key=lambda item: float(item.amount or 0.0), reverse=True)
    bucket_size = max(1, len(ordered_by_amount) // 5)
    largecap_change = mean(float(row.pct_chg or 0.0) for row in ordered_by_amount[:bucket_size])
    smallcap_change = mean(float(row.pct_chg or 0.0) for row in ordered_by_amount[-bucket_size:])
    return MarketBreadthSnapshot(
        breadth_ready=True,
        stock_up_ratio=round(sum(1 for value in changes if value > 0) / len(changes), 4),
        stock_median_change=round(median(changes), 4),
        largecap_change=round(largecap_change, 4),
        smallcap_change=round(smallcap_change, 4),
        style_divergence=round(largecap_change - smallcap_change, 4),
        hot_turnover=hot_turnover,
        hot_overlap_ratio=hot_overlap_ratio,
    )


def _build_local_emotion_snapshot(
    *,
    limit_up_count: int,
    previous_limit_up_count: int,
    board_height: int,
    previous_board_height: int,
    hot_turnover: float,
) -> MarketEmotionSnapshot:
    promotion_ratio = 0.0
    if previous_limit_up_count > 0:
        promotion_ratio = min(1.0, limit_up_count / previous_limit_up_count)
    broken_board_ratio = max(0.0, min(1.0, 1.0 - promotion_ratio)) if previous_limit_up_count > 0 else 0.0
    promotion_break_gap = max(0.0, float(previous_board_height - board_height))
    promotion_break_pressure = max(0.0, min(1.0, broken_board_ratio + hot_turnover * 0.35))
    high_flyer_gap_speed = max(0.0, min(1.0, promotion_break_gap / 3.0))
    high_flyer_retreat_ratio = max(0.0, min(1.0, broken_board_ratio * 0.7 + high_flyer_gap_speed * 0.3))
    return MarketEmotionSnapshot(
        emotion_ready=True,
        limit_up_count=limit_up_count,
        previous_limit_up_count=previous_limit_up_count,
        board_height=board_height,
        previous_board_height=previous_board_height,
        promotion_ratio=round(promotion_ratio, 4),
        broken_board_ratio=round(broken_board_ratio, 4),
        promotion_break_gap=round(promotion_break_gap, 4),
        promotion_break_pressure=round(promotion_break_pressure, 4),
        high_flyer_retreat_ratio=round(high_flyer_retreat_ratio, 4),
        high_flyer_gap_speed=round(high_flyer_gap_speed, 4),
        emotion_distribution_pressure=round(promotion_break_pressure, 4),
    )


def _emotion_counts(signals: list[BoardCandidate]) -> tuple[int, int]:
    if not signals:
        return 0, 0
    return len(signals), max(int(item.board_count or 1) for item in signals)


def _hot_overlap_ratio(current: list[str], previous: list[str]) -> float:
    if not current or not previous:
        return 0.0
    current_set = set(current)
    previous_set = set(previous)
    return round(len(current_set & previous_set) / max(1, len(current_set | previous_set)), 4)


def _limit_down_count(rows: list) -> int:
    return sum(1 for _, row in rows if float(row.pct_chg or 0.0) <= -9.2)


def _evaluate_fast_strategy_date(
    *,
    service: LowBuyScreenerService,
    stat: StrategyBacktestStats,
    strategy: str,
    trade_dates: list[str],
    trade_date: str,
    ranked_pool: list,
    histories: dict[str, pd.DataFrame | None],
    metrics_by_symbol: dict[str, object],
    bars_by_symbol: dict[str, list],
    latest_completed: str,
    hot_industries: list[str],
    market_regime,
    scan_limit: int,
    limit: int,
    forward_days: int,
) -> None:
    completed_dates = [item for item in trade_dates if item <= trade_date]
    retracement_buckets = service._build_retracement_buckets(
        ranked_pool=ranked_pool,
        completed_trade_dates=completed_dates,
        latest_trade_date=trade_date,
        max_days=service._strategy_retracement_days_max(strategy),
    )
    eligible_targets = [
        item
        for bucket in retracement_buckets.values()
        for item in bucket
    ]
    scan_targets = eligible_targets if scan_limit <= 0 else eligible_targets[:scan_limit]
    evaluated: list[LowBuyCandidateOut] = []
    for item in scan_targets:
        history = histories.get(item.symbol)
        metrics = metrics_by_symbol.get(item.symbol)
        if metrics is None:
            continue
        candidate = _evaluate_candidate_from_metrics(
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
            evaluated.append(service._refresh_historical_buy_signal(candidate, history.iloc[latest_rows[-1]]))
    evaluated = service._dedupe_candidates(evaluated)
    evaluated.sort(key=lambda item: (service._signal_rank(item.buy_signal_state), item.score), reverse=True)
    confirmed_candidates = [
        item for item in evaluated if item.buy_signal_state in service._confirmed_signal_states
    ][:12]
    candidates = [
        item for item in evaluated if item.buy_signal_state not in service._confirmed_signal_states
    ][:limit]

    stat.snapshot_count += 1
    stat.snapshot_dates.add(trade_date)
    stat.scanned_count += len(scan_targets)
    stat.matched_count += len(confirmed_candidates) + len(candidates)
    for candidate in _dedupe_candidates_for_backtest(confirmed_candidates + candidates):
        _count_signal_state(stat, candidate.buy_signal_state)
        if candidate.buy_signal_state not in EVALUATED_STATES:
            continue
        outcome = _evaluate_candidate_outcome_from_bars(
            candidate=candidate,
            signal_date=trade_date,
            bars=bars_by_symbol.get(candidate.symbol, []),
            forward_days=forward_days,
        )
        if outcome is None:
            stat.pending_count += 1
            continue
        stat.evaluated_count += 1
        stat.outcomes.append(outcome)


def _evaluate_candidate_from_metrics(
    *,
    service: LowBuyScreenerService,
    item: BoardCandidate,
    latest_trade_date: str,
    strategy: str,
    hot_industries: list[str],
    market_regime,
    metrics,
) -> LowBuyCandidateOut | None:
    if not service._passes_candidate_filters(item):
        return None
    if not passes_common_prefilter(item=item, metrics=metrics, strategy=strategy):
        return None
    if not passes_strategy_prefilter(strategy=strategy, item=item, metrics=metrics):
        return None

    metrics_quality = build_low_buy_metrics_quality(metrics)
    if metrics_quality.quality == "unavailable":
        return None
    base_score = score_candidate(
        strategy=strategy,
        item=item,
        metrics=metrics,
        hot_industries=hot_industries,
    )
    signal_profile = build_signal_family_profile(
        strategy=strategy,
        item=item,
        metrics=metrics,
            hot_industries=hot_industries,
    )
    factor_scores = service._factor_scores(metrics, None)
    context_adjustment = service._build_context_adjustment(
        strategy=strategy,
        item=item,
        metrics=metrics,
        hot_industries=hot_industries,
        market_regime=market_regime,
        signal_profile=signal_profile,
        factor_scores=factor_scores,
        metrics_quality=metrics_quality,
    )
    factor_bonus = service._weighted_factor_bonus(factor_scores)
    adjusted_score = max(
        0.0,
        round(base_score + signal_profile.score_bonus + factor_bonus - context_adjustment.score_penalty, 1),
    )
    if adjusted_score < 74 + context_adjustment.score_floor_shift:
        return None

    setup = build_strategy_setup(strategy=strategy, item=item, metrics=metrics, score=adjusted_score)
    signal_profile = profile_with_setup(signal_profile, setup, strategy=strategy)
    return service._build_candidate_output(
        strategy=strategy,
        item=item,
        metrics=metrics,
        score=adjusted_score,
        setup=setup,
        hot_industries=hot_industries,
        context_adjustment=context_adjustment,
        signal_profile=signal_profile,
        factor_scores=factor_scores,
        metrics_quality=metrics_quality,
    )


def _daily_rows_to_frame(rows, start_date_iso: str) -> pd.DataFrame | None:
    if not rows:
        return None
    frame = pd.DataFrame(
        [
            {
                "date": row.trade_date,
                "open": row.open_price,
                "close": row.close_price,
                "high": row.high_price,
                "low": row.low_price,
                "volume": row.volume,
                "amount": row.amount,
                "pct_chg": row.pct_chg,
            }
            for row in rows
        ]
    )
    frame = frame[frame["date"] >= start_date_iso].copy()
    if frame.empty:
        return None
    for column in ("open", "close", "high", "low", "volume", "amount", "pct_chg"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["open", "close", "high", "low", "volume", "pct_chg"])
    if frame.empty:
        return None
    frame["ma5"] = frame["close"].rolling(5).mean()
    frame["ma10"] = frame["close"].rolling(10).mean()
    frame["ma20"] = frame["close"].rolling(20).mean()
    frame["ma60"] = frame["close"].rolling(60).mean()
    return frame.reset_index(drop=True)


def _history_frame_to_date(
    frame: pd.DataFrame | None,
    trade_date: str,
    *,
    history_window_days: int,
) -> pd.DataFrame | None:
    if frame is None or frame.empty:
        return None
    sliced = frame[frame["date"] <= trade_date]
    if sliced.empty:
        return None
    # Keep enough warm-up bars for MA60 while avoiding repeated large-frame copies.
    max_rows = max(80, min(history_window_days, 760))
    return sliced.tail(max_rows).reset_index(drop=True)


def _dedupe_candidates_for_backtest(candidates: list[LowBuyCandidateOut]) -> list[LowBuyCandidateOut]:
    deduped: dict[tuple[str, str], LowBuyCandidateOut] = {}
    for candidate in candidates:
        deduped[(candidate.strategy_key, candidate.symbol)] = candidate
    return list(deduped.values())


def _evaluate_candidate_outcome_from_bars(
    *,
    candidate: LowBuyCandidateOut,
    signal_date: str,
    bars: list,
    forward_days: int,
) -> TradeOutcome | None:
    signal_index = _bar_index(bars, signal_date)
    if signal_index is None:
        return None
    forward = bars[signal_index + 1 : signal_index + 1 + forward_days]
    if len(forward) < forward_days:
        return None
    entry = max(candidate.entry_zone_low, min(candidate.latest_price, candidate.entry_zone_high))
    if entry <= 0:
        return None
    execution = simulate_candidate_execution(
        candidate=candidate.model_copy(update={"confirmed_trade_date": signal_date}),
        rows=bars,
    )
    event_metrics = _next_day_event_metrics_from_bars(forward=forward, entry=entry)
    return TradeOutcome(
        symbol=candidate.symbol,
        name=candidate.name,
        signal_date=signal_date,
        strategy_key=candidate.strategy_key,
        buy_signal_state=candidate.buy_signal_state,
        entry_price=round(entry, 4),
        execution_status=execution.status,
        net_return_pct=execution.net_return_pct,
        execution_exit_reason=execution.exit_reason,
        return_1d=_close_return(forward, entry, 1),
        return_2d=_close_return(forward, entry, 2),
        return_3d=_close_return(forward, entry, 3),
        return_4d=_close_return(forward, entry, 4),
        return_5d=_close_return(forward, entry, 5),
        max_gain_5d=round((max(row.high_price for row in forward) / entry - 1) * 100, 4),
        max_drawdown_5d=round((min(row.low_price for row in forward) / entry - 1) * 100, 4),
        **event_metrics,
    )


def _bar_index(rows: list, trade_date: str) -> int | None:
    for index, row in enumerate(rows):
        if row.trade_date == trade_date:
            return index
    return None


def _close_return(rows: list, entry: float, holding_days: int) -> float:
    target_index = min(max(holding_days, 1) - 1, len(rows) - 1)
    return round((rows[target_index].close_price / entry - 1) * 100, 4)


def _next_day_event_metrics_from_bars(*, forward: list, entry: float) -> dict[str, Any]:
    if not forward or entry <= 0:
        return _empty_next_day_event_metrics()
    t1 = forward[0]
    t1_high = round((float(t1.high_price) / entry - 1) * 100, 4)
    t1_close = round((float(t1.close_price) / entry - 1) * 100, 4)
    t2_high = 0.0
    t2_close = 0.0
    if len(forward) >= 2:
        t2 = forward[1]
        t2_high = round((float(t2.high_price) / entry - 1) * 100, 4)
        t2_close = round((float(t2.close_price) / entry - 1) * 100, 4)
    return _next_day_event_metrics(
        t1_high=t1_high,
        t1_close=t1_close,
        t2_high=t2_high,
        t2_close=t2_close,
    )


def _next_day_event_metrics_from_frame(*, forward: pd.DataFrame, entry: float) -> dict[str, Any]:
    if forward.empty or entry <= 0:
        return _empty_next_day_event_metrics()
    first = forward.iloc[0]
    t1_high = round((float(first["high"]) / entry - 1) * 100, 4)
    t1_close = round((float(first["close"]) / entry - 1) * 100, 4)
    t2_high = 0.0
    t2_close = 0.0
    if len(forward) >= 2:
        second = forward.iloc[1]
        t2_high = round((float(second["high"]) / entry - 1) * 100, 4)
        t2_close = round((float(second["close"]) / entry - 1) * 100, 4)
    return _next_day_event_metrics(
        t1_high=t1_high,
        t1_close=t1_close,
        t2_high=t2_high,
        t2_close=t2_close,
    )


def _next_day_event_metrics(
    *,
    t1_high: float,
    t1_close: float,
    t2_high: float,
    t2_close: float,
) -> dict[str, Any]:
    return {
        "t1_high_return_pct": t1_high,
        "t1_close_return_pct": t1_close,
        "t1_spike_fade_pct": round(max(0.0, t1_high - t1_close), 4),
        "t2_high_return_pct": t2_high,
        "t2_close_return_pct": t2_close,
        "t1_hit_3_pct": t1_high >= 3.0,
        "t1_hit_5_pct": t1_high >= 5.0,
        "t1_fade_to_entry": t1_high >= 3.0 and t1_close <= 0.0,
    }


def _empty_next_day_event_metrics() -> dict[str, Any]:
    return _next_day_event_metrics(t1_high=0.0, t1_close=0.0, t2_high=0.0, t2_close=0.0)


def _resolve_strategy_keys(raw: str) -> list[str]:
    if raw == "all":
        return list(PLAYBOOKS.keys())
    keys = [item.strip() for item in raw.split(",") if item.strip()]
    unknown = [item for item in keys if item not in PLAYBOOKS]
    if unknown:
        raise SystemExit(f"未知策略: {', '.join(unknown)}")
    return keys


def _evaluation_dates(
    *,
    trade_dates: list[str],
    latest_completed: str,
    months: int,
    forward_days: int,
) -> list[str]:
    start_date = date.today() - timedelta(days=max(1, months) * 31)
    completed_dates = [item for item in trade_dates if item <= latest_completed]
    if len(completed_dates) <= forward_days:
        return []
    last_evaluable = completed_dates[-1 - forward_days]
    return [
        item
        for item in completed_dates
        if item >= start_date.isoformat() and item <= last_evaluable
    ]


def _load_a_share_universe_count(db, service: LowBuyScreenerService) -> int:
    try:
        rows = db.execute(select(DailyBarSnapshot.symbol).distinct()).all()
        local_count = len([row[0] for row in rows if _is_stock_symbol(str(row[0]))])
        if local_count:
            return int(local_count)
    except Exception:
        pass
    try:
        return int(service.market_data.get_total_instruments(db, kind="stock"))
    except Exception:
        return 0


def _load_or_build_snapshot(
    *,
    db,
    service: LowBuyScreenerService,
    strategy: str,
    trade_date: str,
    limit: int,
    scan_limit: int,
    materialization_mode: str,
):
    if materialization_mode == "isolated":
        print(f"[backtest] isolated compute {strategy} {trade_date}", flush=True)
        return service._screen_historical_sync(
            db=db,
            strategy=strategy,
            latest_trade_date=trade_date,
            limit=limit,
            scan_limit=scan_limit,
        )

    payload = service._load_materialized_full_result(
        db=db,
        strategy=strategy,
        latest_trade_date=trade_date,
        limit=limit,
        include_history=False,
    )
    if payload is not None or materialization_mode == "read-only":
        return payload
    print(f"[backtest] {materialization_mode} compute {strategy} {trade_date}", flush=True)
    payload = service._screen_historical_sync(
        db=db,
        strategy=strategy,
        latest_trade_date=trade_date,
        limit=limit,
        scan_limit=scan_limit,
    )
    if materialization_mode != "production":
        return payload
    service._persist_materialized_full_result(db=db, payload=payload)
    db.commit()
    return service._load_materialized_full_result(
        db=db,
        strategy=strategy,
        latest_trade_date=trade_date,
        limit=limit,
        include_history=False,
    )


def _iter_snapshot_candidates(payload) -> list[LowBuyCandidateOut]:
    candidates = list(payload.confirmed_candidates) + list(payload.candidates)
    deduped: dict[tuple[str, str], LowBuyCandidateOut] = {}
    for candidate in candidates:
        deduped[(candidate.strategy_key, candidate.symbol)] = candidate
    return list(deduped.values())


def _count_signal_state(stat: StrategyBacktestStats, state: str) -> None:
    if state in CONFIRMED_STATES:
        stat.confirmed_count += 1
    elif state == "near_entry":
        stat.near_entry_count += 1
    elif state == "watch":
        stat.watch_count += 1
    elif state == "avoid":
        stat.avoid_count += 1


def _evaluate_candidate_outcome(
    *,
    service: LowBuyScreenerService,
    candidate: LowBuyCandidateOut,
    signal_date: str,
    latest_completed: str,
    forward_days: int,
    history_window_days: int,
) -> TradeOutcome | None:
    history = service._load_daily_history(
        symbol=candidate.symbol,
        latest_trade_date=latest_completed,
        history_window_days=history_window_days,
    )
    if history is None or history.empty:
        return None
    matches = history.index[history["date"] == signal_date].tolist()
    if not matches:
        return None
    signal_index = matches[-1]
    forward = history.iloc[signal_index + 1 : signal_index + 1 + forward_days]
    if len(forward) < forward_days:
        return None
    entry = max(candidate.entry_zone_low, min(candidate.latest_price, candidate.entry_zone_high))
    if entry <= 0:
        return None
    execution = simulate_candidate_execution(
        candidate=candidate.model_copy(update={"confirmed_trade_date": signal_date}),
        rows=bars_from_history_frame(history),
    )
    event_metrics = _next_day_event_metrics_from_frame(forward=forward, entry=entry)
    return TradeOutcome(
        symbol=candidate.symbol,
        name=candidate.name,
        signal_date=signal_date,
        strategy_key=candidate.strategy_key,
        buy_signal_state=candidate.buy_signal_state,
        entry_price=round(entry, 4),
        execution_status=execution.status,
        net_return_pct=execution.net_return_pct,
        execution_exit_reason=execution.exit_reason,
        return_1d=round((float(forward.iloc[0]["close"]) / entry - 1) * 100, 4),
        return_2d=round((float(forward.iloc[1]["close"]) / entry - 1) * 100, 4),
        return_3d=round((float(forward.iloc[min(2, len(forward) - 1)]["close"]) / entry - 1) * 100, 4),
        return_4d=round((float(forward.iloc[min(3, len(forward) - 1)]["close"]) / entry - 1) * 100, 4),
        return_5d=round((float(forward.iloc[forward_days - 1]["close"]) / entry - 1) * 100, 4),
        max_gain_5d=round((float(forward["high"].max()) / entry - 1) * 100, 4),
        max_drawdown_5d=round((float(forward["low"].min()) / entry - 1) * 100, 4),
        **event_metrics,
    )


def _build_report(
    *,
    universe_count: int,
    latest_completed: str,
    evaluation_dates: list[str],
    target_profit_pct: float,
    scan_limit: int,
    months: int,
    materialization_mode: str,
    stats: list[StrategyBacktestStats],
) -> dict[str, Any]:
    strategy_rows = [item.as_dict(target_profit_pct=target_profit_pct) for item in stats]
    family_rows = _build_family_rows(stats=stats, target_profit_pct=target_profit_pct)
    all_outcomes = [outcome for item in stats for outcome in item.outcomes]
    snapshot_dates = sorted({trade_date for item in stats for trade_date in item.snapshot_dates})
    materialized_snapshot_count = sum(item.snapshot_count for item in stats)
    expected_snapshot_count = len(evaluation_dates) * len(stats)
    summary = _summary_stats(
        outcomes=all_outcomes,
        target_profit_pct=target_profit_pct,
        scanned_count=sum(item.scanned_count for item in stats),
        matched_count=sum(item.matched_count for item in stats),
        confirmed_count=sum(item.confirmed_count for item in stats),
        near_entry_count=sum(item.near_entry_count for item in stats),
        pending_count=sum(item.pending_count for item in stats),
    )
    summary.update(
        {
            "universe_count": universe_count,
            "evaluation_start": evaluation_dates[0] if evaluation_dates else "",
            "evaluation_end": evaluation_dates[-1] if evaluation_dates else "",
            "evaluation_trade_days": len(evaluation_dates),
            "snapshot_start": snapshot_dates[0] if snapshot_dates else "",
            "snapshot_end": snapshot_dates[-1] if snapshot_dates else "",
            "snapshot_trade_days": len(snapshot_dates),
            "latest_completed_trade_date": latest_completed,
            "scan_limit_per_day": scan_limit,
            "backtest_window_months": months,
            "materialization_mode": materialization_mode,
            "completed_snapshot_count": materialized_snapshot_count,
            "completed_snapshot_coverage_pct": _pct(materialized_snapshot_count, expected_snapshot_count),
            "materialized_snapshot_count": materialized_snapshot_count,
            "failed_snapshot_count": sum(item.failed_snapshot_count for item in stats),
            "expected_snapshot_count": expected_snapshot_count,
            "materialized_snapshot_coverage_pct": _pct(materialized_snapshot_count, expected_snapshot_count),
        }
    )
    return {
        "title": f"低吸策略近 {months} 个月 A 股全市场回测",
        "methodology": [
            "股票池使用 A 股全市场清单计数，策略实际候选由全市场近期涨停/强势结构筛出。",
            "确定买入统计 buy_now / soft_buy_now；接近买点单独统计 near_entry，两类都输出 1/2/3/5 日结果。",
            "真实执行指标按信号后 2 日触达买点、止损/止盈/移动防守退出，并扣除 16bps 成本计算。",
            f"冲高命中按买入后 {PERFORMANCE_FORWARD_DAYS} 个交易日内最高价达到 {target_profit_pct:.1f}% 计算，仅作为辅助观察。",
            "1/2/3/5 日收益按触发日参考入场价到后续收盘价计算，用于持股周期观察。",
            "接近买点样本按买点区参考价估算结果，用于观察信号质量，不等同已经触发买入。",
            f"快照模式：{_materialization_mode_text(materialization_mode)}。",
        ],
        "summary": summary,
        "families": family_rows,
        "strategies": strategy_rows,
        "top_examples": _top_examples(all_outcomes),
    }


def _build_family_rows(
    *,
    stats: list[StrategyBacktestStats],
    target_profit_pct: float,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[StrategyBacktestStats]] = {}
    for item in stats:
        grouped.setdefault(item.strategy_family, []).append(item)
    rows: list[dict[str, Any]] = []
    for family_key, family_stats in grouped.items():
        outcomes = [outcome for item in family_stats for outcome in item.outcomes]
        confirmed_result = _signal_group_stats(
            outcomes=outcomes,
            states=CONFIRMED_STATES,
            target_profit_pct=target_profit_pct,
        )
        near_entry_result = _signal_group_stats(
            outcomes=outcomes,
            states={NEAR_ENTRY_STATE},
            target_profit_pct=target_profit_pct,
        )
        total_result = _signal_group_stats(
            outcomes=outcomes,
            states=EVALUATED_STATES,
            target_profit_pct=target_profit_pct,
        )
        family_text = family_stats[0].strategy_family_text if family_stats else resolve_strategy_family_label(family_key)
        rows.append(
            {
                "strategy_family": family_key,
                "strategy_family_text": family_text,
                "strategy_count": len(family_stats),
                "strategy_titles": [item.strategy_title for item in family_stats],
                "snapshot_count": sum(item.snapshot_count for item in family_stats),
                "failed_snapshot_count": sum(item.failed_snapshot_count for item in family_stats),
                "scanned_count": sum(item.scanned_count for item in family_stats),
                "matched_count": sum(item.matched_count for item in family_stats),
                "confirmed_count": sum(item.confirmed_count for item in family_stats),
                "near_entry_count": sum(item.near_entry_count for item in family_stats),
                "evaluated_count": sum(item.evaluated_count for item in family_stats),
                "pending_count": sum(item.pending_count for item in family_stats),
                "confirmed_result": confirmed_result,
                "near_entry_result": near_entry_result,
                "total_evaluated_result": total_result,
                "conclusion": _strategy_conclusion(
                    confirmed_result["evaluated_count"],
                    confirmed_result["net_win_rate"],
                    confirmed_result["avg_net_return_pct"],
                    confirmed_result["avg_max_drawdown_5d"],
                ),
            }
        )
    rows.sort(
        key=lambda item: (
            item["confirmed_result"]["filled_count"],
            item["confirmed_result"]["net_win_rate"],
            item["confirmed_result"]["avg_net_return_pct"],
        ),
        reverse=True,
    )
    return rows


def _summary_stats(
    *,
    outcomes: list[TradeOutcome],
    target_profit_pct: float,
    scanned_count: int,
    matched_count: int,
    confirmed_count: int,
    near_entry_count: int,
    pending_count: int,
) -> dict[str, Any]:
    evaluated = len(outcomes)
    confirmed_result = _signal_group_stats(
        outcomes=outcomes,
        states=CONFIRMED_STATES,
        target_profit_pct=target_profit_pct,
    )
    near_entry_result = _signal_group_stats(
        outcomes=outcomes,
        states={NEAR_ENTRY_STATE},
        target_profit_pct=target_profit_pct,
    )
    total_result = _signal_group_stats(
        outcomes=outcomes,
        states=EVALUATED_STATES,
        target_profit_pct=target_profit_pct,
    )
    return {
        "scanned_count": scanned_count,
        "matched_count": matched_count,
        "confirmed_count": confirmed_count,
        "near_entry_count": near_entry_count,
        "evaluated_count": evaluated,
        "pending_count": pending_count,
        "confirmed_result": confirmed_result,
        "near_entry_result": near_entry_result,
        "total_evaluated_result": total_result,
        "filled_count": confirmed_result["filled_count"],
        "not_filled_rate": confirmed_result["not_filled_rate"],
        "net_win_rate": confirmed_result["net_win_rate"],
        "avg_net_return_pct": confirmed_result["avg_net_return_pct"],
        "stop_loss_rate": confirmed_result["stop_loss_rate"],
        "hit_count": confirmed_result["hit_count"],
        "hit_rate": confirmed_result["hit_rate"],
        "t1_high_3_hit_rate": confirmed_result["t1_high_3_hit_rate"],
        "t1_high_5_hit_rate": confirmed_result["t1_high_5_hit_rate"],
        "t1_fade_to_entry_rate": confirmed_result["t1_fade_to_entry_rate"],
        "avg_t1_high_return_pct": confirmed_result["avg_t1_high_return_pct"],
        "avg_t1_close_return_pct": confirmed_result["avg_t1_close_return_pct"],
        "avg_t1_spike_fade_pct": confirmed_result["avg_t1_spike_fade_pct"],
        "avg_t2_high_return_pct": confirmed_result["avg_t2_high_return_pct"],
        "avg_t2_close_return_pct": confirmed_result["avg_t2_close_return_pct"],
        "win_rate_1d": confirmed_result["win_rate_1d"],
        "win_rate_2d": confirmed_result["win_rate_2d"],
        "win_rate_3d": confirmed_result["win_rate_3d"],
        "win_rate_4d": confirmed_result["win_rate_4d"],
        "win_rate_5d": confirmed_result["win_rate_5d"],
        "avg_return_1d": confirmed_result["avg_return_1d"],
        "avg_return_2d": confirmed_result["avg_return_2d"],
        "avg_return_3d": confirmed_result["avg_return_3d"],
        "avg_return_4d": confirmed_result["avg_return_4d"],
        "avg_return_5d": confirmed_result["avg_return_5d"],
        "median_return_5d": confirmed_result["median_return_5d"],
        "avg_max_gain_5d": confirmed_result["avg_max_gain_5d"],
        "avg_max_drawdown_5d": confirmed_result["avg_max_drawdown_5d"],
        "profit_factor_5d": confirmed_result["profit_factor_5d"],
        "sample_quality": _sample_quality(evaluated),
        "conclusion": _strategy_conclusion(
            confirmed_result["evaluated_count"],
            confirmed_result["net_win_rate"],
            confirmed_result["avg_net_return_pct"],
            confirmed_result["avg_max_drawdown_5d"],
        ),
    }


def _signal_group_stats(
    *,
    outcomes: list[TradeOutcome],
    states: set[str],
    target_profit_pct: float,
) -> dict[str, Any]:
    scoped = [item for item in outcomes if item.buy_signal_state in states]
    evaluated = len(scoped)
    returns_1d = [item.return_1d for item in scoped]
    returns_2d = [item.return_2d for item in scoped]
    returns_3d = [item.return_3d for item in scoped]
    returns_4d = [item.return_4d for item in scoped]
    returns_5d = [item.return_5d for item in scoped]
    gains_5d = [item.max_gain_5d for item in scoped]
    drawdowns_5d = [item.max_drawdown_5d for item in scoped]
    t1_high_returns = [item.t1_high_return_pct for item in scoped]
    t1_close_returns = [item.t1_close_return_pct for item in scoped]
    t1_spike_fades = [item.t1_spike_fade_pct for item in scoped]
    t2_high_returns = [item.t2_high_return_pct for item in scoped]
    t2_close_returns = [item.t2_close_return_pct for item in scoped]
    wins_5d = [value for value in returns_5d if value > 0]
    losses_5d = [abs(value) for value in returns_5d if value < 0]
    filled = [item for item in scoped if item.execution_status == "filled"]
    not_filled = [item for item in scoped if item.execution_status == "not_filled"]
    net_winners = [item for item in filled if item.net_return_pct > 0]
    net_wins = [item.net_return_pct for item in net_winners]
    net_losses = [abs(item.net_return_pct) for item in filled if item.net_return_pct < 0]
    stop_losses = [item for item in filled if "止损" in item.execution_exit_reason]
    hit_count = sum(1 for item in scoped if item.max_gain_5d >= target_profit_pct)
    return {
        "label": _signal_group_label(states),
        "states": sorted(states),
        "evaluated_count": evaluated,
        "filled_count": len(filled),
        "not_filled_count": len(not_filled),
        "not_filled_rate": _pct(len(not_filled), evaluated),
        "net_win_rate": _pct(len(net_winners), len(filled)),
        "avg_net_return_pct": _avg([item.net_return_pct for item in filled]),
        "stop_loss_rate": _pct(len(stop_losses), len(filled)),
        "execution_profit_factor": _profit_factor(net_wins, net_losses),
        "hit_count": hit_count,
        "hit_rate": _pct(hit_count, evaluated),
        "win_rate_1d": _pct(sum(1 for value in returns_1d if value > 0), evaluated),
        "win_rate_2d": _pct(sum(1 for value in returns_2d if value > 0), evaluated),
        "win_rate_3d": _pct(sum(1 for value in returns_3d if value > 0), evaluated),
        "win_rate_4d": _pct(sum(1 for value in returns_4d if value > 0), evaluated),
        "win_rate_5d": _pct(len(wins_5d), evaluated),
        "avg_return_1d": _avg(returns_1d),
        "avg_return_2d": _avg(returns_2d),
        "avg_return_3d": _avg(returns_3d),
        "avg_return_4d": _avg(returns_4d),
        "avg_return_5d": _avg(returns_5d),
        "median_return_5d": _median(returns_5d),
        "avg_max_gain_5d": _avg(gains_5d),
        "avg_max_drawdown_5d": _avg(drawdowns_5d),
        "t1_high_3_hit_rate": _pct(sum(1 for item in scoped if item.t1_hit_3_pct), evaluated),
        "t1_high_5_hit_rate": _pct(sum(1 for item in scoped if item.t1_hit_5_pct), evaluated),
        "t1_fade_to_entry_rate": _pct(sum(1 for item in scoped if item.t1_fade_to_entry), evaluated),
        "avg_t1_high_return_pct": _avg(t1_high_returns),
        "avg_t1_close_return_pct": _avg(t1_close_returns),
        "avg_t1_spike_fade_pct": _avg(t1_spike_fades),
        "avg_t2_high_return_pct": _avg(t2_high_returns),
        "avg_t2_close_return_pct": _avg(t2_close_returns),
        "profit_factor_5d": _profit_factor(wins_5d, losses_5d),
    }


def _signal_group_label(states: set[str]) -> str:
    for label, group_states in SIGNAL_GROUPS.values():
        if states == group_states:
            return label
    return "合计"


def _history_window_days(months: int, forward_days: int) -> int:
    return max(260, months * 31 + forward_days + 80)


def _top_examples(outcomes: list[TradeOutcome], limit: int = 20) -> list[dict[str, Any]]:
    ordered = sorted(outcomes, key=lambda item: item.max_gain_5d, reverse=True)
    return [item.__dict__ for item in ordered[:limit]]


def _strategy_conclusion(
    evaluated_count: int,
    hit_rate: float,
    avg_return_5d: float,
    avg_max_drawdown_5d: float,
) -> str:
    if evaluated_count < 30:
        return "样本不足，只能作为观察结论。"
    if avg_return_5d > 0.8 and hit_rate >= 50 and avg_max_drawdown_5d > -5.5:
        return "阶段可行，适合继续保留并用仓位控制执行。"
    if avg_return_5d > 0 and hit_rate >= 42:
        return "有一定可行性，但需要继续用市场状态和行业强弱过滤。"
    return "阶段表现不足，生产交易应降权或只保留观察。"


def _sample_quality(evaluated_count: int) -> str:
    if evaluated_count >= 100:
        return "高"
    if evaluated_count >= 30:
        return "中"
    return "低"


def _materialization_mode_text(mode: str) -> str:
    labels = {
        "isolated": "隔离计算，不写入线上物化结果表",
        "production": "写入线上物化结果表，仅用于明确需要回灌缓存的任务",
        "read-only": "只读取已有物化结果，不补算缺失日期",
    }
    return labels.get(mode, mode)


def _avg(values: list[float]) -> float:
    return round(mean(values), 4) if values else 0.0


def _median(values: list[float]) -> float:
    return round(median(values), 4) if values else 0.0


def _pct(part: int, total: int) -> float:
    return round(part / total * 100, 2) if total else 0.0


def _profit_factor(wins: list[float], losses: list[float]) -> float:
    if not losses:
        return round(float(bool(wins)), 4)
    value = sum(wins) / sum(losses)
    return round(value if math.isfinite(value) else 0.0, 4)


def _render_markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"# {report['title']}",
        "",
        "## 结论",
        "",
        f"- 总体判断：{summary['conclusion']}",
        f"- A 股股票数：{summary['universe_count']}",
        f"- 目标回测区间：{summary['evaluation_start']} 至 {summary['evaluation_end']}，共 {summary['evaluation_trade_days']} 个评估交易日",
        f"- 实际快照区间：{summary['snapshot_start']} 至 {summary['snapshot_end']}，共 {summary['snapshot_trade_days']} 个有数据交易日",
        f"- 快照模式：{_materialization_mode_text(summary.get('materialization_mode', ''))}",
        f"- 实际读取/计算快照：{summary['completed_snapshot_count']} / {summary['expected_snapshot_count']}，覆盖率 {summary['completed_snapshot_coverage_pct']}%",
        f"- 回放失败快照：{summary['failed_snapshot_count']}",
        f"- 扫描样本：{summary['scanned_count']}，候选命中：{summary['matched_count']}，确定买入：{summary['confirmed_count']}，接近买点：{summary['near_entry_count']}",
        f"- 已完成评估：{summary['evaluated_count']}，待完成：{summary['pending_count']}，样本质量：{summary['sample_quality']}",
        f"- 确定买入真实执行：成交 {summary['filled_count']}，净胜率 {summary['net_win_rate']}%，均净收益 {summary['avg_net_return_pct']}%，未成交率 {summary['not_filled_rate']}%，止损率 {summary['stop_loss_rate']}%",
        f"- 次日事件验证：T+1 冲高3%命中 {summary['t1_high_3_hit_rate']}%，冲高5%命中 {summary['t1_high_5_hit_rate']}%，冲高回落到买点率 {summary['t1_fade_to_entry_rate']}%，T+1最高均收 {summary['avg_t1_high_return_pct']}%，T+1收盘均收 {summary['avg_t1_close_return_pct']}%，T+2收盘均收 {summary['avg_t2_close_return_pct']}%",
        _render_signal_group_summary("确定买入", summary["confirmed_result"]),
        _render_signal_group_summary("接近买点", summary["near_entry_result"]),
        "",
        "## 口径",
        "",
    ]
    lines.extend(f"- {item}" for item in report["methodology"])
    lines.extend(
        [
            "",
            "## 策略族汇总",
            "",
            "| 策略族 | 策略数 | 类型 | 已评估 | 成交 | 净胜率 | 均净收 | 未成交 | 止损 | 冲高命中 | 1日胜率 | 2日胜率 | 3日胜率 | 4日胜率 | 5日胜率 | 结论 |",
            "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for item in report.get("families", []):
        lines.append(_render_family_group_row(item, "确定买入", item["confirmed_result"]))
        lines.append(_render_family_group_row(item, "接近买点", item["near_entry_result"]))
    lines.extend(
        [
            "",
            "## 策略明细",
            "",
            "| 策略族 | 策略 | 类型 | 快照 | 已评估 | 成交 | 净胜率 | 均净收 | 未成交 | 止损 | 冲高命中 | 1日胜率 | 1日均收 | 2日胜率 | 2日均收 | 3日胜率 | 3日均收 | 4日胜率 | 4日均收 | 5日胜率 | 5日均收 | 最大冲高 | 最大回撤 | 结论 |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for item in report["strategies"]:
        lines.append(_render_strategy_group_row(item, "确定买入", item["confirmed_result"]))
        lines.append(_render_strategy_group_row(item, "接近买点", item["near_entry_result"]))
    return "\n".join(lines) + "\n"


def _render_signal_group_summary(label: str, item: dict[str, Any]) -> str:
    return (
        f"- {label}：已评估 {item['evaluated_count']}，成交 {item['filled_count']}，净胜率 {item['net_win_rate']}%，均净收益 {item['avg_net_return_pct']}%，未成交率 {item['not_filled_rate']}%；"
        f"T+1冲高3%命中 {item['t1_high_3_hit_rate']}%，T+1冲高5%命中 {item['t1_high_5_hit_rate']}%，T+1冲高回落到买点 {item['t1_fade_to_entry_rate']}%；"
        f"5日冲高3%命中 {item['hit_rate']}%；"
        f"胜率 1日 {item['win_rate_1d']}% / 2日 {item['win_rate_2d']}% / 3日 {item['win_rate_3d']}% / 4日 {item['win_rate_4d']}% / 5日 {item['win_rate_5d']}%；"
        f"平均收益 1日 {item['avg_return_1d']}% / 2日 {item['avg_return_2d']}% / 3日 {item['avg_return_3d']}% / 4日 {item['avg_return_4d']}% / 5日 {item['avg_return_5d']}%。"
    )


def _render_strategy_group_row(
    strategy: dict[str, Any],
    label: str,
    result: dict[str, Any],
) -> str:
    return (
        "| {family} | {title} | {label} | {snapshots} | {evaluated} | {filled} | {net_win}% | {net_avg}% | {not_filled}% | {stop_loss}% | {hit}% | "
        "{win1}% | {avg1}% | {win2}% | {avg2}% | {win3}% | {avg3}% | "
        "{win4}% | {avg4}% | {win5}% | {avg5}% | {gain}% | {dd}% | {conclusion} |"
    ).format(
        family=strategy["strategy_family_text"],
        title=strategy["strategy_title"],
        label=label,
        snapshots=strategy["snapshot_count"],
        evaluated=result["evaluated_count"],
        filled=result["filled_count"],
        net_win=result["net_win_rate"],
        net_avg=result["avg_net_return_pct"],
        not_filled=result["not_filled_rate"],
        stop_loss=result["stop_loss_rate"],
        hit=result["hit_rate"],
        win1=result["win_rate_1d"],
        avg1=result["avg_return_1d"],
        win2=result["win_rate_2d"],
        avg2=result["avg_return_2d"],
        win3=result["win_rate_3d"],
        avg3=result["avg_return_3d"],
        win4=result["win_rate_4d"],
        avg4=result["avg_return_4d"],
        win5=result["win_rate_5d"],
        avg5=result["avg_return_5d"],
        gain=result["avg_max_gain_5d"],
        dd=result["avg_max_drawdown_5d"],
        conclusion=strategy["conclusion"] if label == "确定买入" else "观察信号，只用于判断提前量。",
    )


def _render_family_group_row(
    family: dict[str, Any],
    label: str,
    result: dict[str, Any],
) -> str:
    conclusion = family["conclusion"] if label == "确定买入" else "观察信号，只用于判断提前量。"
    return (
        "| {family} | {strategy_count} | {label} | {evaluated} | {filled} | {net_win}% | {net_avg}% | {not_filled}% | {stop_loss}% | {hit}% | "
        "{win1}% | {win2}% | {win3}% | {win4}% | {win5}% | {conclusion} |"
    ).format(
        family=family["strategy_family_text"],
        strategy_count=family["strategy_count"],
        label=label,
        evaluated=result["evaluated_count"],
        filled=result["filled_count"],
        net_win=result["net_win_rate"],
        net_avg=result["avg_net_return_pct"],
        not_filled=result["not_filled_rate"],
        stop_loss=result["stop_loss_rate"],
        hit=result["hit_rate"],
        win1=result["win_rate_1d"],
        win2=result["win_rate_2d"],
        win3=result["win_rate_3d"],
        win4=result["win_rate_4d"],
        win5=result["win_rate_5d"],
        conclusion=conclusion,
    )


if __name__ == "__main__":
    raise SystemExit(main())
