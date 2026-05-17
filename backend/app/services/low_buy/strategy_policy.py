from __future__ import annotations

from enum import Enum


class StrategyTier(str, Enum):
    CORE = "core"
    AUXILIARY = "auxiliary"
    RESEARCH = "research"
    FACTOR = "factor"


CORE_STRATEGIES = frozenset(
    {
        "first_board",
        "volume_shrink",
    }
)

AUXILIARY_STRATEGIES = frozenset(
    {
        "late_session_strong_support",
        "core_midcap_vwap_ma5_retrace",
        "sector_mainline_first_divergence_low_buy",
        "mainline_limitup_shrink_retrace_reclaim",
    }
)

RESEARCH_STRATEGIES = frozenset(
    {
        "classic_retrace",
        "ma_support",
        "breakout_support",
        "limit_up_breakout_retrace",
        "divergence_consensus",
        "ma_channel_band",
        "leader_pullback_band",
        "n_pattern_long_wash",
        "n_pattern_short_wash",
    }
)

FACTOR_STRATEGIES = frozenset(
    {
        "deep_pullback",
        "trend_rebound",
    }
)

PRODUCTION_PRIORITY_STRATEGIES = CORE_STRATEGIES | AUXILIARY_STRATEGIES

STRONG_BUY_PAUSED_STRATEGIES = RESEARCH_STRATEGIES | FACTOR_STRATEGIES

THREE_DAY_PROTECTION_STRATEGIES = CORE_STRATEGIES | AUXILIARY_STRATEGIES

MAINLINE_REQUIRED_STRATEGIES = frozenset(
    {
        "late_session_strong_support",
        "core_midcap_vwap_ma5_retrace",
        "sector_mainline_first_divergence",
        "sector_mainline_first_divergence_low_buy",
        "mainline_limitup_shrink_retrace_reclaim",
    }
)

_TIER_WEIGHTS = {
    StrategyTier.CORE: 1.0,
    StrategyTier.AUXILIARY: 0.65,
    StrategyTier.RESEARCH: 0.0,
    StrategyTier.FACTOR: 0.0,
}


def get_strategy_tier(strategy_key: str) -> StrategyTier:
    if strategy_key in CORE_STRATEGIES:
        return StrategyTier.CORE
    if strategy_key in AUXILIARY_STRATEGIES:
        return StrategyTier.AUXILIARY
    if strategy_key in FACTOR_STRATEGIES:
        return StrategyTier.FACTOR
    return StrategyTier.RESEARCH


def is_core_production(strategy_key: str) -> bool:
    return get_strategy_tier(strategy_key) == StrategyTier.CORE


def is_factor_strategy(strategy_key: str) -> bool:
    return get_strategy_tier(strategy_key) == StrategyTier.FACTOR


def get_tier_weight(strategy_key: str) -> float:
    return _TIER_WEIGHTS[get_strategy_tier(strategy_key)]


def participates_in_priority_board(strategy_key: str) -> bool:
    return get_strategy_tier(strategy_key) in {StrategyTier.CORE, StrategyTier.AUXILIARY}


def strategy_layer(strategy_key: str) -> str:
    tier = get_strategy_tier(strategy_key)
    if tier in {StrategyTier.CORE, StrategyTier.AUXILIARY}:
        return "production"
    if tier == StrategyTier.FACTOR:
        return "research"
    return tier.value


def strong_buy_paused(strategy_key: str) -> bool:
    return get_strategy_tier(strategy_key) in {StrategyTier.RESEARCH, StrategyTier.FACTOR}


def uses_three_day_protection(strategy_key: str) -> bool:
    return get_strategy_tier(strategy_key) in {StrategyTier.CORE, StrategyTier.AUXILIARY}


def requires_mainline_industry(strategy_key: str) -> bool:
    return strategy_key in MAINLINE_REQUIRED_STRATEGIES


def mainline_industry_allowed(
    strategy_key: str,
    industry: str | None,
    hot_industries: list[str] | tuple[str, ...] | None,
) -> bool:
    if not requires_mainline_industry(strategy_key):
        return True
    if not industry or not hot_industries:
        return False
    return industry in hot_industries
