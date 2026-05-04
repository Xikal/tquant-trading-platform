from __future__ import annotations

from app.services.low_buy.shared import LowBuyCandidateOut


def entry_position(candidate: LowBuyCandidateOut, latest_price: float, tolerance_pct: float) -> str:
    if latest_price <= 0:
        return "unknown"
    if latest_price <= candidate.stop_loss * 1.003:
        return "below_stop"
    if candidate.entry_zone_low <= latest_price <= candidate.entry_zone_high:
        return "in_zone"
    if latest_price < candidate.entry_zone_low:
        return "below_zone"
    if tolerance_pct > 0 and latest_price <= candidate.entry_zone_high * (1 + tolerance_pct / 100):
        return "near_above_zone"
    return "above_zone"


def is_strict_in_zone_strategy(strategy_key: str) -> bool:
    return strategy_key in {"limit_up_breakout_retrace"}


def near_entry_positions(strategy_key: str) -> set[str]:
    if is_strict_in_zone_strategy(strategy_key):
        return {"in_zone"}
    return {"in_zone", "below_zone", "near_above_zone"}


def should_avoid_on_entry_position(strategy_key: str, entry_position_value: str) -> bool:
    if not is_strict_in_zone_strategy(strategy_key):
        return False
    return entry_position_value in {"below_zone", "below_stop"}


def below_zone_hard_buy_allowed(candidate: LowBuyCandidateOut) -> bool:
    return candidate.strategy_key in {"classic_retrace", "ma_support", "breakout_support"}


def near_above_soft_buy_allowed(candidate: LowBuyCandidateOut) -> bool:
    return candidate.strategy_key in {"classic_retrace", "ma_support", "breakout_support"}
