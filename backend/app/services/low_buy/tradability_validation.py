from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MinuteExecutionBar:
    trade_date: str
    bar_timestamp: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float = 0.0
    amount: float = 0.0
    pct_chg: float = 0.0
    data_quality: str = "unknown"


@dataclass(frozen=True)
class TickTrade:
    trade_date: str
    trade_timestamp: str
    price: float
    volume: float = 0.0
    amount: float = 0.0
    side: str = ""
    data_quality: str = "unknown"


@dataclass(frozen=True)
class TradabilityCandidate:
    symbol: str
    signal_date: str
    entry_trade_date: str
    exit_trade_date: str
    entry_zone_low: float
    entry_zone_high: float
    entry_price: float
    order_amount: float = 10000.0


@dataclass(frozen=True)
class TradabilityResult:
    tradability_status: str
    fill_price: float | None
    fill_time: str
    slippage_bps: float
    participation_rate_pct: float
    reason: str
    data_quality: str
    limit_state: str
    tick_used: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "tradability_status": self.tradability_status,
            "fill_price": self.fill_price,
            "fill_time": self.fill_time,
            "slippage_bps": self.slippage_bps,
            "participation_rate_pct": self.participation_rate_pct,
            "reason": self.reason,
            "data_quality": self.data_quality,
            "limit_state": self.limit_state,
            "tick_used": self.tick_used,
        }


def replay_candidate_tradability(
    candidate: TradabilityCandidate,
    *,
    minute_bars: list[MinuteExecutionBar],
    tick_trades: list[TickTrade] | None = None,
    max_participation_pct: float = 5.0,
) -> TradabilityResult:
    ticks = sorted(tick_trades or [], key=lambda item: item.trade_timestamp)
    bars = sorted(minute_bars, key=lambda item: item.bar_timestamp)
    if ticks:
        tick_result = _replay_ticks(candidate, ticks, max_participation_pct=max_participation_pct)
        if tick_result.tradability_status == "filled":
            return tick_result
    if not bars:
        return TradabilityResult("data_missing", None, "", 0.0, 0.0, "minute_data_missing", "missing", "unknown", bool(ticks))
    for bar in bars:
        if _locked_limit_up(bar):
            return TradabilityResult("blocked", None, "", 0.0, 0.0, "locked_limit_up", _quality(bars), "locked_limit_up", bool(ticks))
    if all(float(item.volume or 0.0) <= 0 and float(item.amount or 0.0) <= 0 for item in bars):
        return TradabilityResult("blocked", None, "", 0.0, 0.0, "suspended_or_zero_volume", _quality(bars), "suspended", bool(ticks))
    for bar in bars:
        if bar.low_price <= candidate.entry_zone_high and bar.high_price >= candidate.entry_zone_low:
            fill_price = _minute_fill_price(candidate, bar)
            participation = _participation_pct(candidate.order_amount, bar.amount)
            if participation > max_participation_pct:
                return TradabilityResult("blocked", None, bar.bar_timestamp, 0.0, participation, "participation_cap_exceeded", _quality(bars), "normal", bool(ticks))
            return TradabilityResult(
                "filled",
                round(fill_price, 4),
                bar.bar_timestamp,
                _slippage_bps(fill_price, candidate.entry_price),
                participation,
                "minute_touched_entry_zone",
                _quality(bars),
                "normal",
                bool(ticks),
            )
    return TradabilityResult("not_filled", None, "", 0.0, 0.0, "no_entry_zone_touch", _quality(bars), "normal", bool(ticks))


def candidate_from_outcome_row(row: dict[str, Any], *, order_amount: float = 10000.0) -> TradabilityCandidate:
    return TradabilityCandidate(
        symbol=str(row.get("symbol") or ""),
        signal_date=str(row.get("signal_date") or ""),
        entry_trade_date=str(row.get("entry_trade_date") or row.get("signal_date") or ""),
        exit_trade_date=str(row.get("exit_trade_date") or ""),
        entry_zone_low=float(row.get("entry_zone_low") or row.get("entry_price") or 0.0),
        entry_zone_high=float(row.get("entry_zone_high") or row.get("entry_price") or 0.0),
        entry_price=float(row.get("entry_price") or 0.0),
        order_amount=order_amount,
    )


def _replay_ticks(candidate: TradabilityCandidate, ticks: list[TickTrade], *, max_participation_pct: float) -> TradabilityResult:
    for tick in ticks:
        if candidate.entry_zone_low <= tick.price <= candidate.entry_zone_high:
            participation = _participation_pct(candidate.order_amount, tick.amount)
            if participation > max_participation_pct:
                return TradabilityResult("blocked", None, tick.trade_timestamp, 0.0, participation, "participation_cap_exceeded", _tick_quality(ticks), "normal", True)
            return TradabilityResult("filled", round(tick.price, 4), tick.trade_timestamp, _slippage_bps(tick.price, candidate.entry_price), participation, "tick_touched_entry_zone", _tick_quality(ticks), "normal", True)
    return TradabilityResult("not_filled", None, "", 0.0, 0.0, "no_tick_entry_zone_touch", _tick_quality(ticks), "normal", True)


def _minute_fill_price(candidate: TradabilityCandidate, bar: MinuteExecutionBar) -> float:
    if candidate.entry_zone_low <= bar.open_price <= candidate.entry_zone_high:
        return bar.open_price
    if bar.open_price > candidate.entry_zone_high:
        return candidate.entry_zone_high
    return max(bar.open_price, candidate.entry_zone_low)


def _locked_limit_up(bar: MinuteExecutionBar) -> bool:
    return float(bar.pct_chg or 0.0) >= 9.7 and abs(float(bar.high_price) - float(bar.low_price)) <= 0.001


def _participation_pct(order_amount: float, available_amount: float) -> float:
    if available_amount <= 0:
        return 100.0
    return round(order_amount / available_amount * 100.0, 4)


def _slippage_bps(fill_price: float, reference_price: float) -> float:
    if reference_price <= 0:
        return 0.0
    return round((fill_price / reference_price - 1.0) * 10000.0, 4)


def _quality(bars: list[MinuteExecutionBar]) -> str:
    qualities = {str(item.data_quality or "unknown") for item in bars}
    if not bars:
        return "missing"
    if qualities <= {"ok", "fresh", "complete"}:
        return "complete"
    return "partial"


def _tick_quality(ticks: list[TickTrade]) -> str:
    qualities = {str(item.data_quality or "unknown") for item in ticks}
    if not ticks:
        return "missing"
    if qualities <= {"ok", "fresh", "complete"}:
        return "complete"
    return "partial"
