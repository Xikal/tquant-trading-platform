from __future__ import annotations

from typing import Any

from app.services.low_buy.candidate_rule_params import float_param, int_param
from app.services.low_buy.candidate_types import CandidateMetrics


def has_limit_up_distribution_exit(metrics: CandidateMetrics, params: dict[str, Any]) -> bool:
    """Return True when a recent limit-up retrace looks like distribution instead of healthy cooling."""

    if metrics.retracement_days > int_param(params, "distribution_exit_max_retracement_days", 5):
        return False
    if metrics.post_volume_ratio < float_param(params, "distribution_exit_min_post_volume_ratio", 1.0):
        return False
    if metrics.latest_volume_ratio < float_param(params, "distribution_exit_min_latest_volume_ratio", 0.85):
        return False

    pressure_flags = 0
    if metrics.latest_change_pct <= float_param(params, "distribution_exit_max_latest_change_pct", 0.2):
        pressure_flags += 1
    if metrics.close_position_ratio <= float_param(params, "distribution_exit_max_close_position_ratio", 0.48):
        pressure_flags += 1
    if metrics.distribution_risk_score >= float_param(params, "distribution_exit_min_distribution_risk_score", 4.6):
        pressure_flags += 1
    if metrics.consecutive_lower_lows >= int_param(params, "distribution_exit_min_consecutive_lower_lows", 2):
        pressure_flags += 1
    if metrics.weak_close:
        pressure_flags += 1
    if metrics.long_upper_shadow:
        pressure_flags += 1
    if metrics.stall_after_volume_flag:
        pressure_flags += 1
    if metrics.intraday_reversal_flag:
        pressure_flags += 1

    return pressure_flags >= int_param(params, "distribution_exit_min_pressure_flags", 2)
