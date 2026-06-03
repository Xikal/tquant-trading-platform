from __future__ import annotations

ENGINE_VERSION = "trading-experience-v1"

FORBIDDEN_TRADING_COPY = ("买入", "卖出", "加仓", "低吸", "必涨", "推荐", "稳赚")

REVIEW_POOL_MIN_PCT = 8.0
REVIEW_POOL_DROPPED_PCT = -3.0
REVIEW_POOL_RETAINED_PCT = 3.0

VP_POSITION_TAG_CODES = (
    "high_vol_distribution_risk",
    "low_vol_grind_down_risk",
    "healthy_pullback_observe",
    "up_shrink_down_expand_risk",
    "blowoff_overheat_risk",
    "price_volume_divergence_risk",
)

LIMIT_UP_BACKTEST_WINDOW_DAYS = 730
LIMIT_UP_BACKTEST_MIN_CALENDAR_DAYS = 650
LIMIT_UP_BACKTEST_MIN_SAMPLES = 30
LIMIT_UP_BACKTEST_MIN_WINRATE = 0.52
LIMIT_UP_BACKTEST_MIN_PROFIT_FACTOR = 1.2
LIMIT_UP_BACKTEST_MAX_DRAWDOWN_PCT = -20.0
LIMIT_UP_BACKTEST_MIN_STABLE_QUARTERS = 0.5
LIMIT_UP_BACKTEST_SNAPSHOT_TYPE = "limit_up_followthrough_backtest"
LIMIT_UP_BACKTEST_SNAPSHOT_KEY = "all_patterns_24m"

DISCIPLINE_FLAG_KEYS = (
    "trend_follow",
    "stop_loss_set",
    "no_add_down",
    "no_chase_noliquidity",
    "not_against_mainline",
    "planned_position",
)

TRADING_EXPERIENCE_FLAGS = (
    "trading_experience_suite_enabled",
    "trade_review_suite_enabled",
    "vp_position_tags_enabled",
    "relative_strength_board_enabled",
    "holding_discipline_assistant_enabled",
    "limit_up_followthrough_enabled",
    "t_trade_discipline_enabled",
)
