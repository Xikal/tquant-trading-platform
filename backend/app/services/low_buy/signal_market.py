from __future__ import annotations

from app.services.low_buy.market_state_rules import hard_buy_allowed, soft_buy_allowed
from app.services.low_buy.shared import LowBuyCandidateOut


def market_buy_restricted(candidate: LowBuyCandidateOut) -> bool:
    hard_allowed = hard_buy_allowed(
        candidate.strategy_key,
        candidate.market_state,
        candidate.market_state_strength,
    )
    soft_allowed = soft_buy_allowed(
        candidate.strategy_key,
        candidate.market_state,
        candidate.market_state_strength,
    )
    return not hard_allowed and not soft_allowed


def restricted_market_track_allowed(
    candidate: LowBuyCandidateOut,
    entry_position: str,
    entry_distance: float,
) -> bool:
    if candidate.risk_tier in {"block", "degrade"}:
        return False
    if candidate.distribution_risk_score >= 5.8:
        return False
    if candidate.false_breakout_flag or candidate.intraday_reversal_flag:
        return False
    if entry_position == "below_zone" and entry_distance > 0.8:
        return False
    if candidate.score >= 92.0 and entry_position in {"in_zone", "below_zone", "near_above_zone"}:
        return True
    if candidate.score >= 88.0 and entry_position == "near_above_zone" and entry_distance <= 0.65:
        return True
    return (
        candidate.score >= 94.0
        and candidate.leader_rank in {"leader", "strong_follow"}
        and entry_position in {"in_zone", "near_above_zone"}
        and entry_distance <= 0.8
    )
