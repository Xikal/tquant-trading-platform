from __future__ import annotations

from dataclasses import dataclass


VALIDATION_CONFIG_VERSION = "front_row_weighted_v1_2026-05-30_validation"

MIN_FORMAL_OOS_TRADE_DAYS = 60
MIN_FORMAL_OOS_FILLED_COUNT = 150
MIN_FORMAL_OOS_SIGNAL_DAYS = 30

WALK_FORWARD_TRAIN_MONTHS = 12
WALK_FORWARD_VALIDATION_MONTHS = 3
WALK_FORWARD_PURGED_GAP_DAYS = 10
WALK_FORWARD_OOS_TRADE_DAYS = 60
WALK_FORWARD_STEP_TRADE_DAYS = 20
WALK_FORWARD_MIN_WINDOWS = 6
WALK_FORWARD_MIN_PASS_RATE_PCT = 70.0

BASE_ROUND_TRIP_COST_BPS = 16.0
STRESS_EXTRA_COST_BPS = 30.0
EXTREME_EXTRA_COST_BPS = 50.0

GOOD_MARKET_STATES = {"broad_rally", "repair", "weight_support", "weight_support_active"}
WEAK_MARKET_STATES = {"low_volume_wait", "fast_rotation"}
RETREAT_MARKET_STATES = {"high_flyer_retreat", "risk_release", "panic"}
FRONT_ROW_ALLOWED_TIERS = {"core_leader", "leader_hot", "strong_follower"}


@dataclass(frozen=True)
class WeakMarketPolicy:
    name: str
    allow_weak_market: bool
    soft_buy_only: bool
    min_production_score: float
    allowed_front_row_tiers: frozenset[str]
    weak_market_position_cap_pct: float


WEAK_MARKET_POLICIES: dict[str, WeakMarketPolicy] = {
    "weighted_current": WeakMarketPolicy(
        name="weighted_current",
        allow_weak_market=True,
        soft_buy_only=False,
        min_production_score=72.0,
        allowed_front_row_tiers=frozenset(FRONT_ROW_ALLOWED_TIERS),
        weak_market_position_cap_pct=40.0,
    ),
    "weak_soft_only_cap30": WeakMarketPolicy(
        name="weak_soft_only_cap30",
        allow_weak_market=True,
        soft_buy_only=True,
        min_production_score=72.0,
        allowed_front_row_tiers=frozenset(FRONT_ROW_ALLOWED_TIERS),
        weak_market_position_cap_pct=30.0,
    ),
    "weak_soft_score86_cap20": WeakMarketPolicy(
        name="weak_soft_score86_cap20",
        allow_weak_market=True,
        soft_buy_only=True,
        min_production_score=86.0,
        allowed_front_row_tiers=frozenset(FRONT_ROW_ALLOWED_TIERS),
        weak_market_position_cap_pct=20.0,
    ),
    "weak_watch_only": WeakMarketPolicy(
        name="weak_watch_only",
        allow_weak_market=False,
        soft_buy_only=True,
        min_production_score=101.0,
        allowed_front_row_tiers=frozenset(),
        weak_market_position_cap_pct=0.0,
    ),
}

DEFAULT_WEAK_MARKET_POLICY = "weak_soft_score86_cap20"
