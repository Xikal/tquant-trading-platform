from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import MinuteBarSnapshot
from app.services.low_buy.intraday_confirmation import build_intraday_confirmation


@dataclass(frozen=True)
class IntradayEntryInput:
    symbol: str
    strategy_key: str
    trade_date: date
    entry_zone_low: float | None = None
    entry_zone_high: float | None = None
    support_price: float | None = None
    latest_price: float | None = None
    minute_bars: list[Any] | None = None


@dataclass(frozen=True)
class IntradayEntryDecision:
    symbol: str
    strategy_key: str
    trade_date: date
    decision: str
    data_quality: str
    reasons: list[str]
    entry_zone_low: float | None = None
    entry_zone_high: float | None = None
    vwap_distance_pct: float | None = None
    support_distance_pct: float | None = None
    confirmation_text: str = ""
    production_score_delta: float = 0.0

    def as_payload(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "strategy_key": self.strategy_key,
            "trade_date": self.trade_date.isoformat(),
            "decision": self.decision,
            "data_quality": self.data_quality,
            "reasons": list(self.reasons),
            "entry_zone_low": self.entry_zone_low,
            "entry_zone_high": self.entry_zone_high,
            "vwap_distance_pct": self.vwap_distance_pct,
            "support_distance_pct": self.support_distance_pct,
            "confirmation_text": self.confirmation_text,
            "production_score_delta": self.production_score_delta,
        }


def evaluate_intraday_entry(value: IntradayEntryInput) -> IntradayEntryDecision:
    bars = [_as_confirmation_bar(bar) for bar in list(value.minute_bars or [])]
    bars = [bar for bar in bars if bar is not None]
    entry_low = _float_or_none(value.entry_zone_low)
    entry_high = _float_or_none(value.entry_zone_high)
    latest_price = _float_or_none(value.latest_price) or _latest_price(bars)
    support = _float_or_none(value.support_price) or entry_low
    if len(bars) < 5:
        return IntradayEntryDecision(
            symbol=value.symbol,
            strategy_key=value.strategy_key,
            trade_date=value.trade_date,
            decision="no_data",
            data_quality="missing",
            reasons=["分钟数据不足，盘中入场只保留研究态，不加生产分。"],
            entry_zone_low=entry_low,
            entry_zone_high=entry_high,
            confirmation_text="分钟数据缺失",
        )
    confirmation = build_intraday_confirmation(bars)
    vwap_distance = _distance_pct(latest_price, confirmation.vwap)
    support_distance = _distance_pct(latest_price, support)
    if latest_price <= 0 or entry_low is None or entry_high is None or entry_low <= 0 or entry_high <= 0:
        return IntradayEntryDecision(
            symbol=value.symbol,
            strategy_key=value.strategy_key,
            trade_date=value.trade_date,
            decision="no_data",
            data_quality="missing",
            reasons=["入场区间或最新价格缺失，不能生成盘中入场决策。"],
            entry_zone_low=entry_low,
            entry_zone_high=entry_high,
            vwap_distance_pct=vwap_distance,
            support_distance_pct=support_distance,
            confirmation_text=confirmation.reason,
        )
    if latest_price > entry_high * 1.035:
        return IntradayEntryDecision(
            symbol=value.symbol,
            strategy_key=value.strategy_key,
            trade_date=value.trade_date,
            decision="wait",
            data_quality="ok",
            reasons=["价格明显高于计划买点，避免追高，等待回踩入场区。"],
            entry_zone_low=entry_low,
            entry_zone_high=entry_high,
            vwap_distance_pct=vwap_distance,
            support_distance_pct=support_distance,
            confirmation_text=confirmation.reason,
        )
    if latest_price < entry_low * 0.985:
        return IntradayEntryDecision(
            symbol=value.symbol,
            strategy_key=value.strategy_key,
            trade_date=value.trade_date,
            decision="avoid",
            data_quality="ok",
            reasons=["价格跌破计划入场区下沿，先观察支撑是否失效。"],
            entry_zone_low=entry_low,
            entry_zone_high=entry_high,
            vwap_distance_pct=vwap_distance,
            support_distance_pct=support_distance,
            confirmation_text=confirmation.reason,
        )
    if entry_low <= latest_price <= entry_high and confirmation.confirmed:
        return IntradayEntryDecision(
            symbol=value.symbol,
            strategy_key=value.strategy_key,
            trade_date=value.trade_date,
            decision="buy_now",
            data_quality="ok",
            reasons=["价格位于计划入场区且分时承接确认。"],
            entry_zone_low=entry_low,
            entry_zone_high=entry_high,
            vwap_distance_pct=vwap_distance,
            support_distance_pct=support_distance,
            confirmation_text=confirmation.reason,
            production_score_delta=_production_delta(),
        )
    return IntradayEntryDecision(
        symbol=value.symbol,
        strategy_key=value.strategy_key,
        trade_date=value.trade_date,
        decision="wait",
        data_quality="ok",
        reasons=["价格接近入场区，但分时确认不足，等待回踩或重新站稳。"],
        entry_zone_low=entry_low,
        entry_zone_high=entry_high,
        vwap_distance_pct=vwap_distance,
        support_distance_pct=support_distance,
        confirmation_text=confirmation.reason,
    )


def refresh_intraday_entry_snapshots(
    db: Session,
    *,
    symbols: list[str],
    trade_date: date,
    entry_context: dict[str, dict[str, Any]] | None = None,
    bar_period: str = "1m",
    limit: int = 120,
) -> dict[str, Any]:
    contexts = entry_context or {}
    items: list[dict[str, Any]] = []
    no_data = 0
    ready = 0
    for symbol in _clean_symbols(symbols):
        context = contexts.get(symbol) if isinstance(contexts.get(symbol), dict) else {}
        bars = _load_minute_bars(db, symbol=symbol, trade_date=trade_date, bar_period=bar_period, limit=limit)
        latest_price = _float_or_none(context.get("latest_price")) or _latest_price([_as_confirmation_bar(bar) for bar in bars])
        decision = evaluate_intraday_entry(
            IntradayEntryInput(
                symbol=symbol,
                strategy_key=str(context.get("strategy_key") or "unknown"),
                trade_date=trade_date,
                entry_zone_low=_float_or_none(context.get("entry_zone_low")),
                entry_zone_high=_float_or_none(context.get("entry_zone_high")),
                support_price=_float_or_none(context.get("support_price")),
                latest_price=latest_price,
                minute_bars=bars,
            )
        )
        if decision.decision == "no_data":
            no_data += 1
        else:
            ready += 1
        items.append(decision.as_payload())
    return {
        "ok": True,
        "worker_scope": "runtime-worker",
        "status": "ok" if ready else "no_data",
        "gate_owner": "production-traceability-no-research-gate",
        "trade_date": trade_date.isoformat(),
        "item_count": len(items),
        "ready_count": ready,
        "no_data_count": no_data,
        "items": items,
    }


def _load_minute_bars(
    db: Session,
    *,
    symbol: str,
    trade_date: date,
    bar_period: str,
    limit: int,
) -> list[MinuteBarSnapshot]:
    return (
        db.execute(
            select(MinuteBarSnapshot)
            .where(MinuteBarSnapshot.symbol == symbol)
            .where(MinuteBarSnapshot.trade_date == trade_date)
            .where(MinuteBarSnapshot.bar_period == bar_period)
            .order_by(MinuteBarSnapshot.bar_timestamp.asc())
            .limit(max(5, min(int(limit or 120), 240)))
        )
        .scalars()
        .all()
    )


def _as_confirmation_bar(bar: Any) -> Any | None:
    if bar is None:
        return None
    timestamp = getattr(bar, "timestamp", None) or getattr(bar, "bar_timestamp", None)
    open_price = _positive_float(getattr(bar, "open", None), getattr(bar, "open_price", None))
    close = _positive_float(getattr(bar, "close", None), getattr(bar, "close_price", None), getattr(bar, "last_price", None))
    high = _positive_float(getattr(bar, "high", None), getattr(bar, "high_price", None))
    low = _positive_float(getattr(bar, "low", None), getattr(bar, "low_price", None))
    volume = _positive_float(getattr(bar, "volume", None))
    amount = _positive_float(getattr(bar, "amount", None))
    if not timestamp or open_price <= 0 or close <= 0 or high <= 0 or low <= 0:
        return None
    return SimpleNamespace(
        timestamp=str(timestamp),
        open=open_price,
        close=close,
        high=high,
        low=low,
        volume=volume,
        amount=amount,
    )


def _latest_price(bars: list[Any | None]) -> float:
    for bar in reversed([item for item in bars if item is not None]):
        value = _float_or_none(getattr(bar, "close", None) or getattr(bar, "close_price", None) or getattr(bar, "last_price", None))
        if value and value > 0:
            return value
    return 0.0


def _distance_pct(price: float | None, base: float | None) -> float | None:
    price_value = _float_or_none(price)
    base_value = _float_or_none(base)
    if price_value is None or base_value is None or base_value <= 0:
        return None
    return round((price_value / base_value - 1.0) * 100.0, 4)


def _production_delta() -> float:
    settings = get_settings()
    if bool(settings.decision_context_enabled and settings.intraday_entry_production_boost_enabled):
        return 2.0
    return 0.0


def _clean_symbols(symbols: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        value = str(symbol or "").strip()
        if not value or value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result[:80]


def _positive_float(*values: Any) -> float:
    for value in values:
        parsed = _float_or_none(value)
        if parsed is not None and parsed > 0:
            return parsed
    return 0.0


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed
