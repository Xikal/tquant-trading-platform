from __future__ import annotations

from app.services.low_buy.shared import LowBuyCandidateOut


def hard_buy_min_score(candidate: LowBuyCandidateOut) -> float:
    base = {
        "limit_up_breakout_retrace": 88.0,
        "divergence_consensus": 90.0,
    }.get(candidate.strategy_key, 80.0)
    if candidate.risk_tier == "degrade":
        base += 3.0
    return base + max(candidate.dynamic_threshold_adjustment, 0.0)


def soft_buy_min_score(strategy: str, entry_position: str, threshold_shift: float = 0.0) -> float:
    thresholds = {
        "classic_retrace": {"in_zone": 84.0, "near_above_zone": 88.0},
        "ma_support": {"in_zone": 84.0, "near_above_zone": 87.0},
        "first_board": {"in_zone": 86.0, "near_above_zone": 90.0},
        "volume_shrink": {"in_zone": 85.0, "near_above_zone": 89.0},
        "late_session_strong_support": {"in_zone": 86.0, "near_above_zone": 90.0},
        "core_midcap_vwap_ma5_retrace": {"in_zone": 84.0, "near_above_zone": 88.0},
        "sector_mainline_first_divergence_low_buy": {"in_zone": 84.0, "near_above_zone": 88.0},
        "breakout_support": {"in_zone": 84.0, "near_above_zone": 88.0},
        "limit_up_breakout_retrace": {"in_zone": 90.0, "near_above_zone": 94.0},
        "divergence_consensus": {"in_zone": 92.0},
        "deep_pullback": {"in_zone": 88.0, "near_above_zone": 92.0},
        "trend_rebound": {"in_zone": 84.0, "near_above_zone": 87.0},
    }
    strategy_thresholds = thresholds.get(strategy, {})
    return strategy_thresholds.get(entry_position, 88.0) + max(threshold_shift, 0.0)
