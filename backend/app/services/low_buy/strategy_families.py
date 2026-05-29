from __future__ import annotations

STRATEGY_FAMILY_MAP: dict[str, str] = {
    "classic_retrace": "trend_pullback",
    "ma_support": "trend_pullback",
    "volume_shrink": "trend_pullback",
    "late_session_strong_support": "next_day_event",
    "core_midcap_vwap_ma5_retrace": "core_midcap_retrace",
    "sector_mainline_first_divergence_low_buy": "mainline_first_divergence",
    "mainline_limitup_shrink_retrace_reclaim": "mainline_limitup_retrace",
    "ma_channel_band": "trend_support_band",
    "leader_pullback_band": "leader_pullback_band",
    "breakout_support": "breakout_retest",
    "limit_up_breakout_retrace": "breakout_retest",
    "divergence_consensus": "main_wave_confirmation",
    "first_board": "first_board_retest",
    "deep_pullback": "deep_pullback",
    "trend_rebound": "trend_rebound",
    "n_pattern_long_wash": "n_pattern_retrace",
    "n_pattern_short_wash": "n_pattern_retrace",
}

STRATEGY_FAMILY_LABELS: dict[str, str] = {
    "trend_pullback": "趋势回调低吸",
    "next_day_event": "次日兑现模型",
    "core_midcap_retrace": "主线中军回踩",
    "mainline_first_divergence": "主线首分歧",
    "mainline_limitup_retrace": "主线涨停回调",
    "trend_support_band": "均线通道支撑",
    "leader_pullback_band": "龙头回踩波段",
    "breakout_retest": "突破回踩",
    "main_wave_confirmation": "右侧主升确认",
    "first_board_retest": "首板回踩",
    "deep_pullback": "深回撤低吸",
    "trend_rebound": "趋势龙回头",
    "n_pattern_retrace": "N字洗盘回踩",
    "uncategorized": "未分类策略",
}

LOW_BUY_STRATEGY_KEYS: tuple[str, ...] = (
    "classic_retrace",
    "ma_support",
    "first_board",
    "volume_shrink",
    "late_session_strong_support",
    "core_midcap_vwap_ma5_retrace",
    "sector_mainline_first_divergence_low_buy",
    "mainline_limitup_shrink_retrace_reclaim",
    "ma_channel_band",
    "leader_pullback_band",
    "n_pattern_long_wash",
    "n_pattern_short_wash",
    "breakout_support",
    "limit_up_breakout_retrace",
    "divergence_consensus",
    "deep_pullback",
    "trend_rebound",
)


def resolve_strategy_family(strategy_key: str) -> str:
    normalized = (strategy_key or "").strip()
    if not normalized:
        return "uncategorized"
    return STRATEGY_FAMILY_MAP.get(normalized, normalized)


def resolve_strategy_family_label(strategy_key: str) -> str:
    family_key = resolve_strategy_family(strategy_key)
    return STRATEGY_FAMILY_LABELS.get(family_key, family_key)


def family_overlap_multiplier(duplicate_index: int) -> float:
    if duplicate_index <= 0:
        return 1.0
    if duplicate_index == 1:
        return 0.32
    return 0.14


def unclassified_low_buy_strategies(strategy_keys: list[str] | tuple[str, ...] | None = None) -> list[str]:
    keys = strategy_keys or LOW_BUY_STRATEGY_KEYS
    return [
        key
        for key in keys
        if key not in STRATEGY_FAMILY_MAP
        or resolve_strategy_family(key) == "uncategorized"
        or not STRATEGY_FAMILY_LABELS.get(resolve_strategy_family(key))
    ]
