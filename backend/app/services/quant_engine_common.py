from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.schemas import MarketEventOut, QuoteSnapshot


def config_float(config: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(config.get(key, default))
    except (TypeError, ValueError):
        return default


def price_limit_pct(symbol: str, instrument_type: str) -> float:
    if instrument_type == "etf":
        return 10.0
    if symbol.startswith(("300", "688")):
        return 20.0
    if symbol.startswith(("4", "8")):
        return 30.0
    return 10.0


def has_invalid_trade_snapshot(quote: QuoteSnapshot) -> bool:
    if quote.prev_close <= 0 or quote.last_price <= 0:
        return True
    if quote.amount <= 0 and quote.volume <= 0:
        return True
    if quote.open_price <= 0 and quote.high_price <= 0 and quote.low_price <= 0:
        return True
    return False


def calc_tradability(
    quote: QuoteSnapshot,
    amplitude: float,
    volume_ratio_value: float,
    atr_value: float,
) -> float:
    amount_score = min(40.0, quote.amount / 100000000)
    amplitude_score = 30 - abs(amplitude - 4.0) * 4
    volume_score = 20 - abs(volume_ratio_value - 1.8) * 8
    atr_score = min(10.0, atr_value / max(quote.last_price, 0.01) * 100 * 4)
    score = amount_score + amplitude_score + volume_score + atr_score
    return max(0.0, min(100.0, score))


def event_penalty(events: list[MarketEventOut]) -> float:
    penalty_map = {"low": 4, "medium": 10, "high": 22}
    return float(sum(penalty_map.get(event.risk_level, 0) for event in events))


def detect_scenario(timestamp: str, risk_config: dict[str, Any]) -> str:
    try:
        current = datetime.strptime(timestamp[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        return "session_unknown"
    if current.hour < 9 or (current.hour == 9 and current.minute < 30):
        return "pre_open_auction"
    open_phase_end = int(config_float(risk_config, "strategy_open_phase_end_hhmm", 935))
    open_phase_end_hour = max(9, min(15, open_phase_end // 100))
    open_phase_end_minute = max(0, min(59, open_phase_end % 100))
    if (current.hour, current.minute) <= (open_phase_end_hour, open_phase_end_minute):
        return "open_price_discovery"
    if current.hour < 11:
        return "morning_rotation"
    if current.hour < 14:
        return "midday_consolidation"
    return "closing_repricing"


def strategy_note(action: str, turnaround_mode: str) -> str:
    if action == "positive_t":
        if turnaround_mode == "t1":
            return "正T建议以底仓为前提，先加仓再择机卖出原有筹码。"
        return "正T建议适合回踩确认后的低吸加仓。"
    if action == "negative_t":
        if turnaround_mode == "t1":
            return "反T建议以可卖底仓为前提，冲高先减仓，回落再买回。"
        return "反T建议适合冲高钝化后的先卖后买。"
    return "当前更适合等待下一次高质量分时结构。"
