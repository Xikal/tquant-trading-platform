from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StrategyDisplaySeed:
    key: str
    name: str
    description: str
    tier: str
    risk_level: str
    typical_holding_days: str
    sort_order: int
    enabled: bool = True
    probe_status: str = "not_required"
    probe_summary: str = ""
    visibility: str = "full"


DEFAULT_STRATEGY_META: tuple[StrategyDisplaySeed, ...] = (
    StrategyDisplaySeed("first_board", "首板回调", "首板启动后回调承接，偏事件低吸。", "core", "medium", "1-3天", 10),
    StrategyDisplaySeed("volume_shrink", "量能低吸", "放量启动后缩量回踩，等待承接修复。", "core", "medium", "1-3天", 20),
    StrategyDisplaySeed("late_session_strong_support", "收盘强势承接", "主线标的收盘仍有承接，关注次日冲高兑现。", "auxiliary", "medium", "1-2天", 30),
    StrategyDisplaySeed("core_midcap_vwap_ma5_retrace", "中军回踩", "板块核心中军回踩均线/VWAP 附近的低吸研究。", "research", "medium", "2-4天", 40),
    StrategyDisplaySeed("sector_mainline_first_divergence_low_buy", "主线首分歧", "主线板块首次有效分歧后的修复低吸研究。", "research", "high", "1-3天", 50),
    StrategyDisplaySeed("mainline_limitup_shrink_retrace_reclaim", "主线涨停回调", "主线板块涨停启动后，等待缩量回调到均线合一区并重新站回 5 日线。", "research", "medium", "2-5天", 60),
    StrategyDisplaySeed("ma_channel_band", "均线通道波段", "沿 MA20 通道运行的波段研究策略，关注下轨承接与上轨兑现。", "research", "medium", "5-15天", 70),
    StrategyDisplaySeed("leader_pullback_band", "龙头回踩波段", "热点龙头确认后回踩均线支撑的二波研究策略。", "research", "high", "3-10天", 80, probe_status="pending", visibility="backtest_only"),
    StrategyDisplaySeed("n_pattern_long_wash", "长洗N字冲高", "大阳/涨停启动后 7-15 日缩量洗盘，24M 回撤过高，当前只做研究观察。", "research", "high", "3-5天冲高止盈", 90),
    StrategyDisplaySeed("n_pattern_short_wash", "短洗N字冲高", "启动后 2-5 日快速分歧，24M 结果为删除候选，当前只做研究归档。", "research", "high", "1-2天冲高止盈", 100),
)

DEFAULT_STRATEGY_SEEDS_BY_KEY: dict[str, StrategyDisplaySeed] = {
    seed.key: seed for seed in DEFAULT_STRATEGY_META
}

FACTOR_ACCESS_ROLES = {"admin", "administrator", "backtest_optimizer", "backtest_research"}
RESEARCH_ACCESS_ROLES = {"admin", "administrator", "backtest_optimizer", "backtest_research"}
ADMIN_ROLES = {"admin", "administrator"}
RESEARCH_TO_AUXILIARY_GATED_STRATEGIES = {
    "ma_channel_band",
    "leader_pullback_band",
}
RESEARCH_TO_AUXILIARY_MIN_FILLED = 100
RESEARCH_TO_AUXILIARY_MIN_HEALTH = 60.0


def _default_production_strategy_keys() -> list[str]:
    return [
        seed.key
        for seed in DEFAULT_STRATEGY_META
        if seed.enabled and seed.visibility == "full" and seed.tier in {"core", "auxiliary"}
    ]



DEFAULT_PRESETS: tuple[dict[str, Any], ...] = (
    {
        "key": "quick_check",
        "name": "快速体检",
        "description": "全策略最近半年快速扫描，适合日常看策略状态。",
        "sort_order": 10,
        "config": {
            "range": "6m",
            "initial_capital": 500000,
            "strategies": _default_production_strategy_keys(),
            "execution_model": "open_price",
            "max_position_pct": 30,
            "max_single_order_pct": 15,
            "max_positions": 8,
            "max_daily_loss_pct": 5,
            "min_cash_reserve": 5000,
            "stop_loss_pct": -5,
            "take_profit_pct": 10,
            "benchmark": "000300",
        },
    },
    {
        "key": "annual_review",
        "name": "年度回顾",
        "description": "最近 1 年全策略回测，适合复盘策略稳定性。",
        "sort_order": 20,
        "config": {
            "range": "12m",
            "initial_capital": 500000,
            "strategies": _default_production_strategy_keys(),
            "execution_model": "vwap",
            "max_position_pct": 30,
            "max_single_order_pct": 15,
            "max_positions": 8,
            "max_daily_loss_pct": 5,
            "min_cash_reserve": 5000,
            "stop_loss_pct": -5,
            "take_profit_pct": 10,
            "benchmark": "000300",
        },
    },
    {
        "key": "full_validation",
        "name": "完整检验",
        "description": "最近 2 年保守成交模型，适合上线前检查。",
        "sort_order": 30,
        "config": {
            "range": "24m",
            "initial_capital": 500000,
            "strategies": _default_production_strategy_keys(),
            "execution_model": "open_price",
            "max_position_pct": 30,
            "max_single_order_pct": 15,
            "max_positions": 8,
            "max_daily_loss_pct": 5,
            "min_cash_reserve": 5000,
            "stop_loss_pct": -5,
            "take_profit_pct": 10,
            "benchmark": "000300",
        },
    },
)
