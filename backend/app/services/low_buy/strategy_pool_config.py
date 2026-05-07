from __future__ import annotations

from dataclasses import dataclass

from app.services.low_buy.strategy_policy import requires_mainline_industry


BASE_POOL_STRATEGY_KEY = "__base__"
STRATEGY_POOL_SNAPSHOT_VERSION = "pool_v2"


@dataclass(frozen=True)
class StrategyPoolProfile:
    strategy_key: str
    pool_key: str
    title: str
    source: str
    max_size: int = 480
    uses_daily_scan: bool = False
    enabled: bool = True


_STRATEGY_POOL_PROFILES: dict[str, StrategyPoolProfile] = {
    "first_board": StrategyPoolProfile(
        strategy_key="first_board",
        pool_key="limit_up_event_pool",
        title="首板启动池",
        source="limit_up_pool",
    ),
    "volume_shrink": StrategyPoolProfile(
        strategy_key="volume_shrink",
        pool_key="volume_contract_pool",
        title="放量启动后缩量回踩池",
        source="limit_up_pool",
    ),
    "late_session_strong_support": StrategyPoolProfile(
        strategy_key="late_session_strong_support",
        pool_key="mainline_daily_pool",
        title="主线收盘强势承接观察池",
        source="daily_history",
        max_size=360,
        uses_daily_scan=True,
    ),
    "core_midcap_vwap_ma5_retrace": StrategyPoolProfile(
        strategy_key="core_midcap_vwap_ma5_retrace",
        pool_key="mainline_daily_pool",
        title="主线容量中军均线回踩池",
        source="daily_history",
        max_size=360,
        uses_daily_scan=True,
    ),
    "sector_mainline_first_divergence_low_buy": StrategyPoolProfile(
        strategy_key="sector_mainline_first_divergence_low_buy",
        pool_key="mainline_daily_pool",
        title="主线首分歧观察池",
        source="daily_history",
        max_size=360,
        uses_daily_scan=True,
    ),
    "mainline_limitup_shrink_retrace_reclaim": StrategyPoolProfile(
        strategy_key="mainline_limitup_shrink_retrace_reclaim",
        pool_key="mainline_limitup_retrace_pool",
        title="主线涨停缩量回调确认池",
        source="daily_history",
        max_size=320,
        uses_daily_scan=True,
    ),
    "ma_channel_band": StrategyPoolProfile(
        strategy_key="ma_channel_band",
        pool_key="daily_channel_pool",
        title="均线通道波段研究池",
        source="daily_history",
        max_size=160,
        uses_daily_scan=True,
    ),
    "leader_pullback_band": StrategyPoolProfile(
        strategy_key="leader_pullback_band",
        pool_key="leader_pullback_research_pool",
        title="龙头回踩波段研究池",
        source="limit_up_pool",
        max_size=40,
    ),
    "deep_pullback": StrategyPoolProfile(
        strategy_key="deep_pullback",
        pool_key="deep_pullback_research_pool",
        title="主线错杀研究池",
        source="limit_up_pool",
        enabled=False,
    ),
    "limit_up_breakout_retrace": StrategyPoolProfile(
        strategy_key="limit_up_breakout_retrace",
        pool_key="event_research_pool",
        title="涨停事件研究池",
        source="limit_up_pool",
    ),
    "divergence_consensus": StrategyPoolProfile(
        strategy_key="divergence_consensus",
        pool_key="event_research_pool",
        title="分歧事件研究池",
        source="limit_up_pool",
    ),
    "classic_retrace": StrategyPoolProfile(
        strategy_key="classic_retrace",
        pool_key="legacy_research_pool",
        title="历史原始低吸研究池",
        source="limit_up_pool",
    ),
    "ma_support": StrategyPoolProfile(
        strategy_key="ma_support",
        pool_key="legacy_research_pool",
        title="均线辅助因子研究池",
        source="limit_up_pool",
    ),
    "breakout_support": StrategyPoolProfile(
        strategy_key="breakout_support",
        pool_key="legacy_research_pool",
        title="位置支撑研究池",
        source="limit_up_pool",
    ),
    "trend_rebound": StrategyPoolProfile(
        strategy_key="trend_rebound",
        pool_key="legacy_research_pool",
        title="趋势龙回头研究池",
        source="limit_up_pool",
        enabled=False,
    ),
}


def strategy_pool_profile(strategy_key: str) -> StrategyPoolProfile:
    profile = _STRATEGY_POOL_PROFILES.get(strategy_key)
    if profile is not None:
        return profile
    raise ValueError(f"未配置策略样本池: {strategy_key}")


def strategy_pool_key(strategy_key: str) -> str:
    return strategy_pool_profile(strategy_key).pool_key


def strategy_pool_title(strategy_key: str) -> str:
    return strategy_pool_profile(strategy_key).title


def strategy_uses_daily_scan_pool(strategy_key: str) -> bool:
    return strategy_pool_profile(strategy_key).uses_daily_scan


def strategy_pool_requires_mainline(strategy_key: str) -> bool:
    return requires_mainline_industry(strategy_key)


def strategy_pool_enabled(strategy_key: str) -> bool:
    return strategy_pool_profile(strategy_key).enabled
