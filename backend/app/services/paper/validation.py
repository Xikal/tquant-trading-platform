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
from app.services.paper.matching import MatchResult, OrderSide, OrderType, PaperMatchingEngine


class StrategyValidationPipeline:
    """Replay materialized strategy signals with paper matching semantics."""

    def __init__(self, db: Session, matching_engine: PaperMatchingEngine | None = None) -> None:
        self.db = db
        self.matching = matching_engine or PaperMatchingEngine()

    def validate(self, payload: StrategyValidationRequest) -> StrategyValidationReport:
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
        )
        run = self._persist_report("strategy-validation", payload.model_dump(), report.model_dump(mode="json"))
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
    return StrategyValidationItem(
        strategy_key=strategy_key,
        evaluated_signals=evaluated_signals,
        filled_signals=len(records),
        win_rate_pct=_rate(len(wins), len(records)),
        net_win_rate_pct=_rate(len(wins) - len(losses), len(records)),
        avg_return_pct=round(sum(returns) / len(returns), 3) if returns else 0.0,
        profit_factor=round(gross_gain / gross_loss, 3) if gross_loss > 0 else None,
        max_drawdown_pct=round(min((item.max_drawdown_pct for item in records), default=0.0), 3),
        pbo_risk=_pbo_risk(records),
        by_market_state=_market_state_buckets(records),
    )


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
    midpoint = len(records) // 2
    first = _avg_return(records[:midpoint])
    second = _avg_return(records[midpoint:])
    if first > 0 and second > 0:
        return "low"
    if first * second < 0:
        return "high"
    return "medium"


def _avg_return(records: list[ReplayRecord]) -> float:
    return sum(item.return_pct for item in records) / max(len(records), 1)


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


def _comparison_summary(items: list[StrategyValidationItem]) -> str:
    if not items:
        return "暂无可对比策略。"
    return f"策略对比已按平均收益和净胜率排序，当前排名第一：{items[0].strategy_key}。"
