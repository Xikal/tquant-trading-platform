from __future__ import annotations

from dataclasses import dataclass


PRODUCTION_SCORING_CONFIG_VERSION = "front_row_weighted_policy_v2_2026-05-30"
PRODUCTION_SCORING_VALIDATION_CONFIG_VERSION = "front_row_weighted_policy_v2_2026-05-30_validation"

BASE_PRODUCTION_SCORE = 50.0
BASE_WATCH_SCORE = 45.0
DEFAULT_SCORE_CAP = 100.0
SHADOW_CONFIRM_SCORE_THRESHOLD = 72.0
PORTFOLIO_CANDIDATE_SCORE_THRESHOLD = 82.0
WEAK_MARKET_VALIDATION_POLICY = "weak_soft_score86_cap20"
WEAK_MARKET_VALIDATION_SCORE_THRESHOLD = 86.0
WEAK_MARKET_VALIDATION_POSITION_CAP_PCT = 20.0

PRODUCTION_SIGNAL_WEIGHTS: dict[str, float | None] = {
    "soft_buy_now": 16.0,
    "buy_now": 8.0,
    "observe_confirmed": None,
    "near_entry": None,
    "watch": None,
    "avoid": None,
}

WATCH_SIGNAL_WEIGHTS: dict[str, float] = {
    "soft_buy_now": 14.0,
    "buy_now": 10.0,
    "observe_confirmed": 6.0,
    "near_entry": 10.0,
    "watch": 2.0,
    "avoid": -20.0,
}

PRODUCTION_STRATEGY_PRIORS: dict[str, float] = {
    "first_board": 14.0,
    "volume_shrink": 5.0,
    "late_session_strong_support": 3.0,
}

WATCH_STRATEGY_PRIORS: dict[str, float] = {
    "first_board": 12.0,
    "ma_channel_band": 12.0,
    "leader_pullback_band": 10.0,
    "volume_shrink": 6.0,
    "deep_pullback": 8.0,
    "n_pattern_long_wash": 6.0,
    "classic_retrace": 4.0,
    "ma_support": 4.0,
    "late_session_strong_support": 5.0,
    "core_midcap_vwap_ma5_retrace": 4.0,
    "breakout_support": 3.0,
    "limit_up_breakout_retrace": 2.0,
    "trend_rebound": 2.0,
    "n_pattern_short_wash": 1.0,
    "divergence_consensus": 1.0,
    "sector_mainline_first_divergence_low_buy": 1.0,
    "mainline_limitup_shrink_retrace_reclaim": 1.0,
}

FRONT_ROW_PRODUCTION_WEIGHTS: dict[str, float] = {
    "core_leader": 14.0,
    "leader_hot": 10.0,
    "strong_follower": 5.0,
    "middle": 0.0,
    "laggard": -8.0,
    "cold_laggard": -14.0,
    "unknown": -2.0,
}

FRONT_ROW_WATCH_WEIGHTS: dict[str, float] = {
    "core_leader": 12.0,
    "leader_hot": 9.0,
    "strong_follower": 6.0,
    "middle": 2.0,
    "laggard": -4.0,
    "cold_laggard": -8.0,
    "unknown": 0.0,
}

FRONT_ROW_INTERACTION_WEIGHTS: dict[str, float] = {
    "first_board": 6.0,
    "late_session_strong_support": 3.0,
    "volume_shrink": 0.0,
}

FRONT_ROW_INTERACTION_TIERS = {"core_leader", "leader_hot", "strong_follower"}

MARKET_PRODUCTION_WEIGHTS: dict[str, float] = {
    "broad_rally": 8.0,
    "repair": 6.0,
    "weight_support_active": 4.0,
    "fast_rotation": -4.0,
    "low_volume_wait": -8.0,
    "high_flyer_retreat": -18.0,
    "risk_release": -18.0,
    "unknown": -2.0,
}

MARKET_WATCH_WEIGHTS: dict[str, float] = {
    "broad_rally": 6.0,
    "repair": 5.0,
    "weight_support_active": 4.0,
    "fast_rotation": -2.0,
    "low_volume_wait": -4.0,
    "high_flyer_retreat": -10.0,
    "risk_release": -10.0,
    "unknown": 0.0,
}

RETREAT_MARKET_STATES = {"high_flyer_retreat", "risk_release"}
WEAK_MARKET_STATES = {"low_volume_wait", "fast_rotation"}
LAGGARD_TIERS = {"laggard", "cold_laggard"}

@dataclass(frozen=True)
class ProductionScoringCaps:
    laggard: float = 68.0
    weak_market_laggard: float = 55.0
    retreat_market: float = 50.0
    low_sample_strategy: float = 74.0
    non_production_strategy: float = 0.0


CAPS = ProductionScoringCaps()
