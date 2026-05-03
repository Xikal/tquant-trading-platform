from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.entities import BacktestRun, LowBuyResultSnapshot
from app.models.schema_defs.research import (
    StrategyComparisonRequest,
    StrategyValidationItem,
    StrategyValidationReport,
    StrategyValidationRequest,
)
from app.repositories.low_buy import DailyHistoryRepository
from app.repositories.low_buy.results import LowBuyResultRepository
from app.services.low_buy.risk_metrics import compute_pbo
from app.services.paper.matching import MatchResult, OrderSide, OrderType, PaperMatchingEngine


class StrategyValidationPipeline:
    """Replay materialized strategy signals with paper matching semantics."""

    def __init__(self, db: Session, matching_engine: PaperMatchingEngine | None = None) -> None:
        self.db = db
        self.matching = matching_engine or PaperMatchingEngine()

    def validate(
        self,
        payload: StrategyValidationRequest,
        *,
        run_name: str = "strategy-validation",
        extra_params: dict | None = None,
    ) -> StrategyValidationReport:
        trade_dates = DailyHistoryRepository(self.db).fetch_recent_trade_dates(payload.lookback_days)
        items = [
            self._validate_strategy(strategy_key=strategy, trade_dates=trade_dates, payload=payload)
            for strategy in _unique_strategies(payload.strategies)
        ]
        report = StrategyValidationReport(
            generated_at=datetime.now(),
            lookback_days=payload.lookback_days,
            strategy_count=len(items),
            total_filled_signals=sum(item.filled_signals for item in items),
            items=items,
            summary=_summary_text(items),
            policy_recommendations=_policy_recommendations(items),
        )
        params = payload.model_dump()
        if extra_params:
            params.update(extra_params)
        run = self._persist_report(run_name, params, report.model_dump(mode="json"))
        return report.model_copy(update={"run_id": run.id})

    def compare_strategies(self, payload: StrategyComparisonRequest) -> StrategyValidationReport:
        request = StrategyValidationRequest(
            strategies=[payload.baseline_strategy, *payload.candidate_strategies],
            lookback_days=payload.lookback_days,
        )
        report = self.validate(request)
        ranked = sorted(
            report.items,
            key=lambda item: (item.avg_return_pct, item.net_win_rate_pct, item.filled_signals),
            reverse=True,
        )
        return report.model_copy(update={"items": ranked, "summary": _comparison_summary(ranked)})

    def _validate_strategy(
        self,
        *,
        strategy_key: str,
        trade_dates: list[str],
        payload: StrategyValidationRequest,
    ) -> StrategyValidationItem:
        rows = LowBuyResultRepository(self.db).fetch_confirmed_results_for_dates(
            latest_trade_dates=trade_dates,
            strategy_key=strategy_key,
            limit_per_date=payload.max_signals_per_day,
        )
        records = self._simulate_rows(rows)
        return _item_from_records(strategy_key=strategy_key, evaluated_signals=len(rows), records=records)

    def _simulate_rows(self, rows: list[LowBuyResultSnapshot]) -> list[ReplayRecord]:
        symbols = sorted({row.symbol for row in rows})
        if not symbols:
            return []
        start_date = min(str(row.latest_trade_date) for row in rows)
        end_date = DailyHistoryRepository(self.db).fetch_recent_trade_dates(1)[-1]
        histories = DailyHistoryRepository(self.db).fetch_rows_for_symbols(symbols, start_date, end_date)
        records: list[ReplayRecord] = []
        for row in rows:
            bars = histories.get(row.symbol, [])
            record = self._simulate_row(row, bars)
            if record is not None:
                records.append(record)
        return records

    def _simulate_row(self, row: LowBuyResultSnapshot, bars) -> ReplayRecord | None:
        entry_index = _find_trade_date_index(bars, str(row.latest_trade_date))
        if entry_index is None or entry_index + 1 >= len(bars):
            return None
        entry_bar = bars[entry_index]
        exit_bar = bars[min(entry_index + 3, len(bars) - 1)]
        entry_price = _entry_price(row, entry_bar.close_price)
        if entry_price <= 0:
            return None
        match = self.matching.match(
            symbol=row.symbol,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
            limit_price=None,
            current_price=Decimal(str(entry_price)),
            quote_time=datetime.now(),
            is_suspended=False,
        )
        if match.result != MatchResult.FILLED or match.avg_fill_price is None:
            return None
        fill_price = float(match.avg_fill_price)
        exit_price = float(exit_bar.close_price or 0)
        if exit_price <= 0:
            return None
        return_pct = (exit_price - fill_price) / fill_price * 100
        max_drawdown_pct = _max_drawdown_after_entry(fill_price, bars[entry_index + 1 : min(entry_index + 6, len(bars))])
        payload = _safe_json_loads(row.payload_json)
        return ReplayRecord(
            return_pct=round(return_pct, 4),
            max_drawdown_pct=round(max_drawdown_pct, 4),
            market_state=str(payload.get("market_state") or "unknown"),
        )

    def _persist_report(self, name: str, params: dict, result: dict) -> BacktestRun:
        row = BacktestRun(
            name=name,
            params_json=json.dumps(params, ensure_ascii=False),
            result_json=json.dumps(result, ensure_ascii=False),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row


@dataclass(frozen=True)
class ReplayRecord:
    return_pct: float
    max_drawdown_pct: float
    market_state: str


def _item_from_records(strategy_key: str, evaluated_signals: int, records: list[ReplayRecord]) -> StrategyValidationItem:
    returns = [item.return_pct for item in records]
    wins = [value for value in returns if value > 0]
    losses = [value for value in returns if value < 0]
    gross_gain = sum(wins)
    gross_loss = abs(sum(losses))
    in_sample, out_sample = _train_test_split(records)
    sharpe = _sharpe_ratio(returns)
    walk_forward = _walk_forward(records)
    pbo_detail = _pbo_detail(real_sharpe=sharpe, returns=returns)
    return StrategyValidationItem(
        strategy_key=strategy_key,
        evaluated_signals=evaluated_signals,
        filled_signals=len(records),
        win_rate_pct=_rate(len(wins), len(records)),
        net_win_rate_pct=_rate(len(wins) - len(losses), len(records)),
        avg_return_pct=round(sum(returns) / len(returns), 3) if returns else 0.0,
        in_sample_return_pct=round(_avg_return(in_sample), 3),
        out_sample_return_pct=round(_avg_return(out_sample), 3),
        out_sample_win_rate_pct=_rate(sum(1 for item in out_sample if item.return_pct > 0), len(out_sample)),
        profit_factor=round(gross_gain / gross_loss, 3) if gross_loss > 0 else None,
        sharpe_ratio=round(sharpe, 4),
        max_drawdown_pct=round(min((item.max_drawdown_pct for item in records), default=0.0), 3),
        walk_forward_windows=walk_forward["windows"],
        walk_forward_pass_rate_pct=walk_forward["pass_rate_pct"],
        pbo_risk=_pbo_risk(records),
        pbo_probability=_pbo_probability(in_sample, out_sample, pbo_detail),
        pbo_detail=pbo_detail,
        by_market_state=_market_state_buckets(records),
    )


def _train_test_split(records: list[ReplayRecord]) -> tuple[list[ReplayRecord], list[ReplayRecord]]:
    if len(records) < 2:
        return records, []
    split_index = max(1, int(len(records) * 0.7))
    return records[:split_index], records[split_index:]


def _market_state_buckets(records: list[ReplayRecord]) -> dict[str, dict[str, float]]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for item in records:
        buckets[item.market_state or "unknown"].append(item.return_pct)
    return {
        key: {
            "filled_signals": len(values),
            "win_rate_pct": _rate(sum(1 for value in values if value > 0), len(values)),
            "avg_return_pct": round(sum(values) / len(values), 3) if values else 0.0,
        }
        for key, values in buckets.items()
    }


def _pbo_risk(records: list[ReplayRecord]) -> str:
    if len(records) < 30:
        return "insufficient_sample"
    first, second = _train_test_split(records)
    first_return = _avg_return(first)
    second_return = _avg_return(second)
    if first_return > 0 and second_return > 0:
        return "low"
    if first_return * second_return < 0:
        return "high"
    return "medium"


def _avg_return(records: list[ReplayRecord]) -> float:
    return sum(item.return_pct for item in records) / max(len(records), 1)


def _pbo_probability(
    in_sample: list[ReplayRecord],
    out_sample: list[ReplayRecord],
    pbo_detail: dict,
) -> float | None:
    pbo = pbo_detail.get("pbo")
    if isinstance(pbo, (int, float)) and pbo_detail.get("verdict") != "insufficient_sample":
        return round(1.0 - float(pbo), 4)
    if len(in_sample) < 20 or len(out_sample) < 10:
        return None
    in_return = _avg_return(in_sample)
    out_return = _avg_return(out_sample)
    if in_return > 0 and out_return > 0:
        return 0.15
    if in_return > 0 >= out_return:
        return 0.75
    if in_return * out_return < 0:
        return 0.65
    return 0.45


def _pbo_detail(*, real_sharpe: float, returns: list[float]) -> dict:
    if len(returns) < 30:
        return {"verdict": "insufficient_sample", "pbo": None}
    # Treat each filled signal as an active event and compare against randomized
    # event placement on the same return distribution.  Cap permutations to keep
    # route latency predictable for interactive validation.
    return compute_pbo(
        real_sharpe=real_sharpe,
        signal_series=_validation_signal_mask(len(returns)),
        returns_series=returns,
        n_permutations=300,
    )


def _validation_signal_mask(size: int) -> list[bool]:
    if size <= 0:
        return []
    # Leave room for permutation; using every row as active makes PBO degenerate.
    active_count = max(1, min(size - 1, int(size * 0.7)))
    return [index < active_count for index in range(size)]


def _sharpe_ratio(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    std = variance**0.5
    if std <= 0:
        return 0.0
    # Daily short-horizon validation uses percent returns; annualize by sqrt(252).
    return (mean / std) * (252**0.5)


def _walk_forward(records: list[ReplayRecord], windows: int = 5) -> dict[str, float | int]:
    if not records:
        return {"windows": 0, "pass_rate_pct": 0.0}
    actual_windows = max(1, min(windows, len(records)))
    window_size = max(1, len(records) // actual_windows)
    chunks = [
        records[index : index + window_size]
        for index in range(0, len(records), window_size)
    ][:actual_windows]
    passed = sum(1 for chunk in chunks if _avg_return(chunk) > 0)
    return {
        "windows": len(chunks),
        "pass_rate_pct": _rate(passed, len(chunks)),
    }


def _entry_price(row: LowBuyResultSnapshot, fallback_close: float) -> float:
    payload = _safe_json_loads(row.payload_json)
    for key in ("latest_price", "entry_price", "buy_price"):
        value = _as_float(payload.get(key))
        if value > 0:
            return value
    entry_zone = str(payload.get("entry_zone") or "")
    if "-" in entry_zone:
        values = [_as_float(part) for part in entry_zone.split("-")]
        values = [value for value in values if value > 0]
        if values:
            return sum(values) / len(values)
    return float(fallback_close or 0.0)


def _find_trade_date_index(bars, trade_date: str) -> int | None:
    for index, item in enumerate(bars):
        if str(item.trade_date) == trade_date:
            return index
    return None


def _max_drawdown_after_entry(entry_price: float, bars) -> float:
    if entry_price <= 0:
        return 0.0
    lows = [float(item.low_price or 0.0) for item in bars if float(item.low_price or 0.0) > 0]
    if not lows:
        return 0.0
    return (min(lows) - entry_price) / entry_price * 100


def _safe_json_loads(raw: str | None) -> dict:
    try:
        payload = json.loads(raw or "{}")
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _as_float(value) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _rate(part: int, total: int) -> float:
    return round(part / total * 100, 3) if total else 0.0


def _unique_strategies(strategies: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for strategy in strategies:
        key = strategy.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result


def _summary_text(items: list[StrategyValidationItem]) -> str:
    if not items:
        return "暂无可验证策略。"
    best = max(items, key=lambda item: (item.avg_return_pct, item.net_win_rate_pct, item.filled_signals))
    return f"已完成 {len(items)} 个策略验证，当前样本内表现较好的是 {best.strategy_key}。"


def _policy_recommendations(items: list[StrategyValidationItem]) -> dict[str, str]:
    return {item.strategy_key: _policy_recommendation(item) for item in items}


def _policy_recommendation(item: StrategyValidationItem) -> str:
    if item.filled_signals < 20:
        return "observe_insufficient_sample"
    if item.avg_return_pct <= 0 or item.net_win_rate_pct < 0:
        return "downgrade_review_required"
    if item.profit_factor is not None and item.profit_factor < 1.1:
        return "downgrade_profit_factor_weak"
    if item.walk_forward_pass_rate_pct < 50:
        return "observe_walk_forward_unstable"
    return "keep_production"


def _comparison_summary(items: list[StrategyValidationItem]) -> str:
    if not items:
        return "暂无可对比策略。"
    return f"策略对比已按平均收益和净胜率排序，当前排名第一：{items[0].strategy_key}。"
