from __future__ import annotations

from app.services.low_buy.candidate_rule_params import (
    ma5_ma10_ma20_confluence_pct,
    prefilter_params,
)
from app.services.low_buy.candidate_types import CandidateMetrics
from app.services.low_buy.research_layers import passes_research_prefilter
from app.services.low_buy.shared import BoardCandidate, LOW_BUY_THRESHOLDS
from app.services.low_buy.strategy_policy import StrategyTier, get_strategy_tier


def passes_strategy_prefilter(
    strategy: str,
    item: BoardCandidate,
    metrics: CandidateMetrics,
) -> bool:
    strategy_tier = get_strategy_tier(strategy)
    if strategy_tier == StrategyTier.CORE and item.amount < LOW_BUY_THRESHOLDS.MIN_DAILY_AMOUNT_CORE:
        return False
    if strategy_tier == StrategyTier.AUXILIARY and item.amount < LOW_BUY_THRESHOLDS.MIN_DAILY_AMOUNT_AUXILIARY:
        return False
    if strategy == "classic_retrace":
        params = prefilter_params(strategy)
        return (
            item.board_count <= params["max_board_count"]
            and params["min_retracement_days"] <= metrics.retracement_days <= params["max_retracement_days"]
            and metrics.board_low_held
            and metrics.volume_burst_ratio >= params["min_volume_burst_ratio"]
            and metrics.support_distance_pct <= params["max_support_distance_pct"]
            and metrics.latest_close >= metrics.ma10 * params["min_close_to_ma10_ratio"]
            and metrics.distribution_risk_score < params["max_distribution_risk_score"]
            and not metrics.false_breakout_flag
            and (metrics.shrink_basic_ok or metrics.momentum_exhaustion or metrics.post_volume_ratio <= params["max_post_volume_ratio_relaxed"])
        )
    if strategy == "ma_support":
        params = prefilter_params(strategy)
        return (
            item.board_count <= params["max_board_count"]
            and params["min_retracement_days"] <= metrics.retracement_days <= params["max_retracement_days"]
            and (metrics.trend_ok or metrics.latest_close >= metrics.ma20 * params["min_close_to_ma20_ratio"])
            and metrics.latest_close >= metrics.ma20 * params["min_close_to_ma20_ratio"]
            and (
                min(metrics.close_to_ma5, metrics.close_to_ma10) <= params["max_close_to_ma5_ma10_pct"]
                or metrics.close_to_ma20 <= params["max_close_to_ma20_pct"]
            )
            and metrics.support_distance_pct <= params["max_support_distance_pct"]
        )
    if strategy == "first_board":
        params = prefilter_params(strategy)
        return (
            item.board_count == params["required_board_count"]
            and params["min_retracement_days"] <= metrics.retracement_days <= params["max_retracement_days"]
            and metrics.board_low_held
            and metrics.volume_burst_ratio >= params["min_volume_burst_ratio"]
            and metrics.latest_close <= metrics.board_high * (1 + params["max_close_above_board_high_pct"] / 100.0)
            and metrics.distribution_risk_score < params["max_distribution_risk_score"]
            and not metrics.false_breakout_flag
            and not metrics.intraday_reversal_flag
        )
    if strategy == "volume_shrink":
        params = prefilter_params(strategy)
        return (
            item.board_count <= params["max_board_count"]
            and params["min_retracement_days"] <= metrics.retracement_days <= params["max_retracement_days"]
            and metrics.volume_burst_ratio >= params["min_volume_burst_ratio"]
            and (metrics.shrink_staircase or metrics.shrink_basic_ok)
            and metrics.latest_volume_ratio <= params["max_latest_volume_ratio"]
            and metrics.post_volume_ratio <= params["max_post_volume_ratio"]
            and metrics.support_distance_pct <= params["max_support_distance_pct"]
            and metrics.latest_close >= metrics.ma20 * params["min_close_to_ma20_ratio"]
            and metrics.distribution_risk_score < params["max_distribution_risk_score"]
            and not metrics.false_breakout_flag
            and not metrics.intraday_reversal_flag
        )
    if strategy == "late_session_strong_support":
        return _passes_late_session_support_prefilter(item, metrics)
    if strategy == "core_midcap_vwap_ma5_retrace":
        return _passes_core_midcap_retrace_prefilter(item, metrics)
    if strategy == "sector_mainline_first_divergence_low_buy":
        return _passes_mainline_first_divergence_prefilter(item, metrics)
    if strategy == "mainline_limitup_shrink_retrace_reclaim":
        return _passes_mainline_limitup_shrink_retrace_prefilter(item, metrics)
    if strategy == "ma_channel_band":
        return _passes_ma_channel_band_prefilter(item, metrics)
    if strategy == "leader_pullback_band":
        return _passes_leader_pullback_band_prefilter(item, metrics)
    if strategy == "breakout_support":
        params = prefilter_params(strategy)
        return (
            params["min_retracement_days"] <= metrics.retracement_days <= params["max_retracement_days"]
            and metrics.breakout_level > 0
            and metrics.breakout_distance_pct <= params["max_breakout_distance_pct"]
            and metrics.latest_close >= metrics.breakout_level * params["min_close_to_breakout_ratio"]
            and metrics.latest_change_pct <= params["max_latest_change_pct"]
        )
    if strategy == "limit_up_breakout_retrace":
        return passes_research_prefilter(strategy, item, metrics)
    if strategy == "divergence_consensus":
        return passes_research_prefilter("divergence_consensus", item, metrics)
    if strategy == "deep_pullback":
        params = prefilter_params(strategy)
        return (
            item.board_count <= params["max_board_count"]
            and metrics.strong_trend
            and params["min_retracement_days"] <= metrics.retracement_days <= params["max_retracement_days"]
            and params["min_drawdown_from_board_pct"] <= metrics.drawdown_from_board_pct <= params["max_drawdown_from_board_pct"]
            and metrics.support_distance_ma20_pct <= params["max_support_distance_ma20_pct"]
            and metrics.latest_close >= metrics.recent_low_guard
        )
    if strategy == "trend_rebound":
        params = prefilter_params(strategy)
        return (
            params["min_retracement_days"] <= metrics.retracement_days <= params["max_retracement_days"]
            and (metrics.strong_trend or (metrics.trend_ok and metrics.latest_close >= metrics.ma20 * params["min_close_to_ma20_ratio"]))
            and metrics.latest_close >= metrics.ma10 * params["min_close_to_ma10_ratio"]
            and metrics.drawdown_from_board_pct >= params["min_drawdown_from_board_pct"]
        )
    return False


def _passes_late_session_support_prefilter(item: BoardCandidate, metrics: CandidateMetrics) -> bool:
    params = prefilter_params("late_session_strong_support")
    return (
        item.amount >= params["min_amount"]
        and params["min_retracement_days"]
        <= metrics.retracement_days
        <= params["max_retracement_days"]
        and params["min_latest_change_pct"] <= metrics.latest_change_pct <= params["max_latest_change_pct"]
        and metrics.close_position_ratio >= params["min_close_position_ratio"]
        and metrics.support_distance_pct <= params["max_support_distance_pct"]
        and metrics.latest_volume_ratio <= params["max_latest_volume_ratio"]
        and metrics.post_volume_ratio <= params["max_post_volume_ratio"]
        and metrics.distribution_risk_score < params["max_distribution_risk_score"]
        and (metrics.trend_ok or metrics.strong_trend)
        and not metrics.long_upper_shadow
        and not metrics.weak_close
        and not metrics.false_breakout_flag
    )


def _passes_core_midcap_retrace_prefilter(item: BoardCandidate, metrics: CandidateMetrics) -> bool:
    ma_distance = min(metrics.close_to_ma5, metrics.close_to_ma10)
    params = prefilter_params("core_midcap_vwap_ma5_retrace")
    return (
        item.amount >= params["min_amount"]
        and params["min_retracement_days"]
        <= metrics.retracement_days
        <= params["max_retracement_days"]
        and (metrics.strong_trend or metrics.trend_ok)
        and ma_distance <= params["max_ma_distance_pct"]
        and metrics.support_distance_pct <= params["max_support_distance_pct"]
        and params["min_latest_change_pct"] <= metrics.latest_change_pct <= params["max_latest_change_pct"]
        and metrics.latest_volume_ratio <= params["max_latest_volume_ratio"]
        and metrics.post_volume_ratio <= params["max_post_volume_ratio"]
        and metrics.distribution_risk_score < params["max_distribution_risk_score"]
        and not metrics.false_breakout_flag
        and not metrics.intraday_reversal_flag
    )


def _passes_mainline_first_divergence_prefilter(item: BoardCandidate, metrics: CandidateMetrics) -> bool:
    params = prefilter_params("sector_mainline_first_divergence_low_buy")
    return (
        item.board_count <= params["max_board_count"]
        and item.amount >= params["min_amount"]
        and params["min_retracement_days"]
        <= metrics.retracement_days
        <= params["max_retracement_days"]
        and metrics.volume_burst_ratio >= params["min_volume_burst_ratio"]
        and params["min_latest_change_pct"] <= metrics.latest_change_pct <= params["max_latest_change_pct"]
        and metrics.support_distance_pct <= params["max_support_distance_pct"]
        and metrics.latest_volume_ratio <= params["max_latest_volume_ratio"]
        and metrics.post_volume_ratio <= params["max_post_volume_ratio"]
        and metrics.board_low_held
        and metrics.distribution_risk_score < params["max_distribution_risk_score"]
        and not metrics.long_upper_shadow
        and not metrics.weak_close
        and not metrics.false_breakout_flag
    )


def _passes_mainline_limitup_shrink_retrace_prefilter(item: BoardCandidate, metrics: CandidateMetrics) -> bool:
    params = prefilter_params("mainline_limitup_shrink_retrace_reclaim")
    ma_confluence_pct = ma5_ma10_ma20_confluence_pct(metrics)
    structure_ready = (
        ma_confluence_pct <= params["max_ma_confluence_pct"]
        or (
            metrics.support_touch_count >= params["min_support_touch_count"]
            and metrics.support_distance_pct <= params["max_support_distance_pct"]
        )
    )
    return (
        item.board_count <= params["max_board_count"]
        and item.amount >= params["min_amount"]
        and params["min_retracement_days"]
        <= metrics.retracement_days
        <= params["max_retracement_days"]
        and metrics.volume_burst_ratio >= params["min_volume_burst_ratio"]
        and metrics.board_low_held
        and metrics.latest_close >= metrics.ma5 * params["min_close_to_ma5_ratio"]
        and metrics.latest_close <= metrics.ma5 * (1 + params["max_close_above_ma5_pct"] / 100.0)
        and structure_ready
        and metrics.support_distance_pct <= params["max_support_distance_pct"]
        and metrics.latest_volume_ratio <= params["max_latest_volume_ratio"]
        and metrics.post_volume_ratio <= params["max_post_volume_ratio"]
        and metrics.distribution_risk_score < params["max_distribution_risk_score"]
        and params["min_latest_change_pct"] <= metrics.latest_change_pct <= params["max_latest_change_pct"]
        and not metrics.long_upper_shadow
        and not metrics.weak_close
        and not metrics.false_breakout_flag
        and not metrics.intraday_reversal_flag
    )


def _passes_ma_channel_band_prefilter(item: BoardCandidate, metrics: CandidateMetrics) -> bool:
    params = prefilter_params("ma_channel_band")
    return (
        item.amount >= params["min_amount"]
        and metrics.platform_window_days >= params["min_platform_days"]
        and params["min_retracement_days"]
        <= metrics.retracement_days
        <= params["max_retracement_days"]
        and metrics.ma20 > metrics.ma60
        and metrics.latest_close >= metrics.ma20 * params["min_close_to_ma20_ratio"]
        and metrics.close_to_ma20 <= params["max_ma20_distance_pct"]
        and metrics.latest_volume_ratio <= params["max_latest_volume_ratio"]
        and metrics.post_volume_ratio <= params["max_post_volume_ratio"]
        and metrics.distribution_risk_score < params["max_distribution_risk_score"]
        and metrics.support_distance_pct <= params["max_support_distance_pct"]
        and not metrics.false_breakout_flag
        and not metrics.intraday_reversal_flag
    )


def _passes_leader_pullback_band_prefilter(item: BoardCandidate, metrics: CandidateMetrics) -> bool:
    params = prefilter_params("leader_pullback_band")
    excluded_prefixes = tuple(str(value) for value in params.get("exclude_symbol_prefixes", ()))
    return (
        item.board_count <= params["max_board_count"]
        and not item.symbol.startswith(excluded_prefixes)
        and item.amount >= params["min_amount"]
        and params["min_retracement_days"]
        <= metrics.retracement_days
        <= params["max_retracement_days"]
        and metrics.volume_burst_ratio >= params["min_volume_burst_ratio"]
        and (metrics.strong_trend or metrics.latest_close >= metrics.ma20 * params["min_close_to_ma20_ratio"])
        and metrics.board_low_held
        and metrics.support_distance_pct <= params["max_support_distance_pct"]
        and metrics.latest_volume_ratio <= params["max_latest_volume_ratio"]
        and metrics.post_volume_ratio <= params["max_post_volume_ratio"]
        and metrics.distribution_risk_score < params["max_distribution_risk_score"]
        and not metrics.false_breakout_flag
        and not metrics.long_upper_shadow
    )
