from __future__ import annotations

from typing import Any

from app.services.low_buy.candidate_rule_params import execution_params, float_param
from app.services.low_buy.candidate_types import CandidateContextAdjustment, CandidateMetrics


N_PATTERN_CONFIRMATION_STRATEGIES = {"n_pattern_long_wash", "n_pattern_short_wash"}
_BLOCKED_MARKET_STATES = {"risk_release", "fast_rotation", "high_flyer_retreat"}


def observation_confirmation_ready(
    *,
    strategy: str,
    setup_ready: bool,
    metrics: CandidateMetrics,
    context: CandidateContextAdjustment,
) -> bool:
    if strategy not in N_PATTERN_CONFIRMATION_STRATEGIES:
        return setup_ready
    if not setup_ready or context.execution_blocked:
        return False
    params = execution_params(strategy)
    if not _market_and_sector_allowed(params=params, context=context):
        return False
    if not _distribution_clear(metrics=metrics, params=params):
        return False
    if strategy == "n_pattern_long_wash":
        return _long_wash_confirmed(metrics=metrics, params=params)
    return _short_wash_confirmed(metrics=metrics, params=params)


def _market_and_sector_allowed(params: dict[str, Any], context: CandidateContextAdjustment) -> bool:
    market_state = str(context.market_state or "")
    if market_state in _BLOCKED_MARKET_STATES:
        return False
    allowed_states = set(params.get("allowed_market_states") or ["broad_rally", "repair", "warm"])
    if market_state not in allowed_states:
        return False
    hot_tiers = set(params.get("hot_industry_tiers") or ["core_hot", "secondary_hot"])
    return str(context.industry_tier or "") in hot_tiers


def _distribution_clear(*, metrics: CandidateMetrics, params: dict[str, Any]) -> bool:
    max_distribution = float_param(params, "max_distribution_risk_score", 4.8)
    if metrics.distribution_risk_score >= max_distribution:
        return False
    if metrics.false_breakout_flag or metrics.stall_after_volume_flag or metrics.intraday_reversal_flag:
        return False
    if metrics.long_upper_shadow and metrics.latest_volume_ratio >= 0.85:
        return False
    if metrics.weak_close and metrics.latest_volume_ratio >= 0.75:
        return False
    if metrics.consecutive_lower_lows >= 2 and metrics.latest_volume_ratio >= 0.75:
        return False
    return metrics.post_volume_ratio <= 1.0


def _long_wash_confirmed(*, metrics: CandidateMetrics, params: dict[str, Any]) -> bool:
    low_hold = float_param(params, "min_board_low_hold_ratio", 1.005)
    repair_to_wash = float_param(params, "min_repair_to_wash_volume_ratio", 1.2)
    max_latest_volume = float_param(params, "max_latest_volume_ratio", 1.25)
    min_close_position = float_param(params, "min_close_position_ratio", 0.60)
    ma_reclaimed = metrics.latest_close >= metrics.ma5 or metrics.latest_close >= metrics.ma10
    return (
        metrics.latest_low >= metrics.board_low * low_hold
        and metrics.post_volume_ratio <= float_param(params, "max_post_volume_ratio", 0.72)
        and metrics.latest_volume_ratio >= metrics.post_volume_ratio * repair_to_wash
        and metrics.latest_volume_ratio <= max_latest_volume
        and metrics.close_position_ratio >= min_close_position
        and metrics.latest_change_pct >= float_param(params, "min_latest_change_pct", 0.8)
        and ma_reclaimed
    )


def _short_wash_confirmed(*, metrics: CandidateMetrics, params: dict[str, Any]) -> bool:
    low_hold = float_param(params, "min_board_low_hold_ratio", 1.0)
    max_upper_shadow = float_param(params, "max_divergence_upper_shadow_ratio", 0.32)
    return (
        metrics.latest_low >= metrics.board_low * low_hold
        and metrics.latest_volume_ratio <= float_param(params, "max_latest_volume_ratio", 0.92)
        and metrics.support_distance_pct <= float_param(params, "max_support_distance_pct", 3.2)
        and metrics.close_position_ratio >= float_param(params, "min_close_position_ratio", 0.58)
        and metrics.upper_shadow_ratio <= max_upper_shadow
        and not metrics.divergence_day_stall
        and (metrics.doji_like or metrics.long_lower_shadow)
    )
