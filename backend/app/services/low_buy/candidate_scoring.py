from __future__ import annotations

from app.services.low_buy.candidate_rule_params import (
    float_param,
    int_param,
    ma5_ma10_ma20_confluence_pct,
    scoring_params,
    strategy_score_params,
)
from app.services.low_buy.candidate_types import CandidateMetrics
from app.services.low_buy.shared import BoardCandidate


def compute_score(
    board_count: int,
    retracement_days: int,
    volume_burst_ratio: float,
    volume_shrink_ratio: float,
    support_distance_pct: float,
    latest_change_pct: float,
) -> float:
    params = scoring_params()
    score = float_param(params, "base_score", 70.0)
    score += min(
        max(volume_burst_ratio - float_param(params, "volume_burst_base", 1.2), 0.0),
        float_param(params, "volume_burst_cap", 2.0),
    ) * float_param(params, "volume_burst_weight", 8.0)
    score += min(
        max(float_param(params, "volume_shrink_base", 0.85) - volume_shrink_ratio, 0.0),
        float_param(params, "volume_shrink_cap", 0.5),
    ) * float_param(params, "volume_shrink_weight", 24.0)
    score += max(0.0, float_param(params, "support_distance_base", 2.4) - support_distance_pct) * float_param(
        params, "support_distance_weight", 4.5
    )
    score += max(0.0, float_param(params, "latest_change_base", 1.8) - abs(latest_change_pct)) * float_param(
        params, "latest_change_weight", 3.2
    )
    retracement_bonus = params.get("retracement_bonus", {})
    if isinstance(retracement_bonus, dict):
        score += float_param(retracement_bonus, str(retracement_days), 0.0)
    if board_count == 1:
        score += float_param(params, "first_board_bonus", 6.0)
    elif board_count >= int_param(params, "high_board_count_threshold", 3):
        score += float_param(params, "high_board_penalty", -4.0)
    return round(max(0.0, min(float_param(params, "max_score", 99.0), score)), 1)


def score_candidate(
    strategy: str,
    item: BoardCandidate,
    metrics: CandidateMetrics,
    hot_industries: list[str],
) -> float:
    score = compute_score(
        board_count=item.board_count,
        retracement_days=metrics.retracement_days,
        volume_burst_ratio=metrics.volume_burst_ratio,
        volume_shrink_ratio=metrics.post_volume_ratio,
        support_distance_pct=metrics.support_distance_pct,
        latest_change_pct=metrics.latest_change_pct,
    )
    scoring = scoring_params()
    global_bonuses = scoring.get("global_bonuses", {})
    global_bonuses = global_bonuses if isinstance(global_bonuses, dict) else {}
    strategy_bonus = strategy_score_params(strategy)
    is_hot_industry = bool(item.industry and hot_industries and item.industry in hot_industries)
    if metrics.strong_trend:
        score += float_param(global_bonuses, "strong_trend", 5.2)
    if is_hot_industry:
        score += float_param(global_bonuses, "hot_industry", 3.5)
    if metrics.shrink_staircase:
        score += float_param(global_bonuses, "shrink_staircase", 2.8)
    if strategy == "ma_support" and metrics.support_distance_pct <= float_param(strategy_bonus, "support_distance_max_pct", 1.6):
        score += float_param(strategy_bonus, "bonus", 4.0)
    if (
        strategy == "first_board"
        and item.board_count == 1
        and metrics.retracement_days <= int_param(strategy_bonus, "max_retracement_days", 3)
    ):
        score += float_param(strategy_bonus, "bonus", 5.0)
    if (
        strategy == "volume_shrink"
        and metrics.volume_burst_ratio >= float_param(strategy_bonus, "min_volume_burst_ratio", 2.0)
        and metrics.shrink_staircase
    ):
        score += float_param(strategy_bonus, "bonus", 5.5)
    if strategy == "late_session_strong_support":
        score += max(0.0, metrics.close_position_ratio - float_param(strategy_bonus, "close_position_base", 0.55)) * float_param(
            strategy_bonus, "close_position_weight", 12.0
        )
        score += float_param(strategy_bonus, "positive_change_bonus", 3.0) if metrics.latest_change_pct >= 0 else 0.0
        score += (
            float_param(strategy_bonus, "latest_volume_bonus", 2.5)
            if metrics.latest_volume_ratio <= float_param(strategy_bonus, "latest_volume_max", 0.95)
            else 0.0
        )
    if strategy == "core_midcap_vwap_ma5_retrace":
        score += float_param(strategy_bonus, "strong_trend_bonus", 4.0) if metrics.strong_trend else float_param(
            strategy_bonus, "trend_ok_bonus", 2.0
        )
        score += max(0.0, float_param(strategy_bonus, "ma_distance_base", 1.8) - min(metrics.close_to_ma5, metrics.close_to_ma10)) * float_param(
            strategy_bonus, "ma_distance_weight", 2.5
        )
        score += (
            float_param(strategy_bonus, "large_amount_bonus", 2.5)
            if item.amount >= float_param(strategy_bonus, "large_amount_threshold", 800_000_000.0)
            else 0.0
        )
    if strategy == "sector_mainline_first_divergence_low_buy":
        score += float_param(strategy_bonus, "first_board_bonus", 4.0) if item.board_count == 1 else float_param(
            strategy_bonus, "non_first_board_bonus", 1.5
        )
        score += max(0.0, float_param(strategy_bonus, "post_volume_base", 1.2) - metrics.post_volume_ratio) * float_param(
            strategy_bonus, "post_volume_weight", 4.0
        )
        score += float_param(strategy_bonus, "board_low_held_bonus", 2.5) if metrics.board_low_held else 0.0
    if strategy == "mainline_limitup_shrink_retrace_reclaim":
        ma_confluence_pct = ma5_ma10_ma20_confluence_pct(metrics)
        score += float_param(strategy_bonus, "first_board_bonus", 4.0) if item.board_count == 1 else float_param(
            strategy_bonus, "non_first_board_bonus", 1.5
        )
        score += max(0.0, float_param(strategy_bonus, "ma_confluence_base", 2.2) - ma_confluence_pct) * float_param(
            strategy_bonus, "ma_confluence_weight", 2.2
        )
        score += min(
            max(metrics.support_touch_count - int_param(strategy_bonus, "support_touch_offset", 1), 0),
            int_param(strategy_bonus, "support_touch_cap", 2),
        ) * float_param(strategy_bonus, "support_touch_weight", 1.8)
        score += max(0.0, float_param(strategy_bonus, "post_volume_base", 0.95) - metrics.post_volume_ratio) * float_param(
            strategy_bonus, "post_volume_weight", 8.0
        )
        score += float_param(strategy_bonus, "close_above_ma5_bonus", 3.0) if metrics.latest_close >= metrics.ma5 else 0.0
        score += float_param(strategy_bonus, "board_low_held_bonus", 2.0) if metrics.board_low_held else 0.0
    if strategy == "ma_channel_band":
        score += max(0.0, float_param(strategy_bonus, "ma20_distance_base", 3.2) - metrics.close_to_ma20) * float_param(
            strategy_bonus, "ma20_distance_weight", 2.0
        )
        score += float_param(strategy_bonus, "close_above_ma20_bonus", 3.0) if metrics.latest_close >= metrics.ma20 else 0.0
        score += float_param(strategy_bonus, "trend_ok_bonus", 2.0) if metrics.trend_ok else 0.0
    if strategy == "leader_pullback_band":
        score += float_param(strategy_bonus, "strong_trend_bonus", 4.0) if metrics.strong_trend else float_param(
            strategy_bonus, "trend_ok_bonus", 1.5
        )
        score += float_param(strategy_bonus, "board_low_held_bonus", 3.0) if metrics.board_low_held else 0.0
        score += min(
            max(metrics.volume_burst_ratio - float_param(strategy_bonus, "volume_burst_base", 1.5), 0.0),
            float_param(strategy_bonus, "volume_burst_cap", 1.5),
        ) * float_param(strategy_bonus, "volume_burst_weight", 2.5)
    if strategy == "n_pattern_long_wash":
        score += float_param(strategy_bonus, "board_low_held_bonus", 3.0) if metrics.board_low_held else 0.0
        score += max(0.0, float_param(strategy_bonus, "post_volume_base", 0.82) - metrics.post_volume_ratio) * float_param(
            strategy_bonus, "post_volume_weight", 10.0
        )
        score += max(0.0, metrics.close_position_ratio - float_param(strategy_bonus, "close_position_base", 0.50)) * float_param(
            strategy_bonus, "close_position_weight", 8.0
        )
        if metrics.retracement_days >= int_param(strategy_bonus, "long_wash_day_min", 8):
            score += float_param(strategy_bonus, "long_wash_day_bonus", 2.0)
    if strategy == "n_pattern_short_wash":
        score += float_param(strategy_bonus, "board_low_held_bonus", 2.5) if metrics.board_low_held else 0.0
        if metrics.doji_like or metrics.long_lower_shadow:
            score += float_param(strategy_bonus, "reversal_candle_bonus", 4.0)
        score += max(0.0, metrics.close_position_ratio - float_param(strategy_bonus, "close_position_base", 0.45)) * float_param(
            strategy_bonus, "close_position_weight", 7.0
        )
        if metrics.retracement_days <= int_param(strategy_bonus, "short_wash_day_max", 4):
            score += float_param(strategy_bonus, "short_wash_day_bonus", 2.0)
    if strategy == "breakout_support" and metrics.breakout_distance_pct <= float_param(strategy_bonus, "breakout_distance_max_pct", 2.0):
        score += float_param(strategy_bonus, "bonus", 4.0)
    if strategy == "limit_up_breakout_retrace":
        if metrics.platform_breakout_pct >= float_param(strategy_bonus, "platform_breakout_min_pct", 2.0):
            score += float_param(strategy_bonus, "platform_breakout_bonus", 6.0)
        if metrics.post_volume_ratio <= float_param(strategy_bonus, "post_volume_max", 0.68):
            score += float_param(strategy_bonus, "post_volume_bonus", 4.0)
        if metrics.doji_like or metrics.long_lower_shadow:
            score += float_param(strategy_bonus, "reversal_candle_bonus", 4.0)
    if strategy == "divergence_consensus":
        score += float_param(strategy_bonus, "breakout_bonus", 5.0) if metrics.consensus_breakout else float_param(
            strategy_bonus, "no_breakout_penalty", -8.0
        )
        score += min(
            max(metrics.consensus_volume_ratio - float_param(strategy_bonus, "volume_ratio_base", 1.4), 0.0),
            float_param(strategy_bonus, "volume_ratio_cap", 1.2),
        ) * float_param(strategy_bonus, "volume_ratio_weight", 4.0)
        score += max(0.0, float_param(strategy_bonus, "consolidation_volume_base", 0.72) - metrics.consolidation_volume_ratio) * float_param(
            strategy_bonus, "consolidation_volume_weight", 12.0
        )
        score += (
            float_param(strategy_bonus, "close_strength_bonus", 3.0)
            if metrics.consensus_close_strength >= float_param(strategy_bonus, "close_strength_min", 0.68)
            else 0.0
        )
        score += float_param(strategy_bonus, "hot_industry_bonus", 2.0) if is_hot_industry else 0.0
    if (
        strategy == "deep_pullback"
        and float_param(strategy_bonus, "min_drawdown_pct", -8.5)
        <= metrics.drawdown_from_board_pct
        <= float_param(strategy_bonus, "max_drawdown_pct", -3.0)
    ):
        score += float_param(strategy_bonus, "bonus", 5.0)
    if (
        strategy == "trend_rebound"
        and metrics.latest_close >= metrics.ma10
        and metrics.retracement_days >= int_param(strategy_bonus, "min_retracement_days", 2)
    ):
        score += float_param(strategy_bonus, "bonus", 4.0)
    return round(max(0.0, min(99.0, score)), 1)
