from __future__ import annotations

from typing import Any

from app.services.low_buy.candidate_rule_params import execution_params, float_param
from app.services.low_buy.candidate_types import CandidateContextAdjustment, CandidateMetrics


N_PATTERN_CONFIRMATION_STRATEGIES = {"n_pattern_long_wash", "n_pattern_short_wash"}


def observation_confirmation_ready(
    *,
    strategy: str,
    setup_ready: bool,
    metrics: CandidateMetrics,
    context: CandidateContextAdjustment,
) -> bool:
    if strategy not in N_PATTERN_CONFIRMATION_STRATEGIES:
        return setup_ready
    if not setup_ready:
        return False
    params = execution_params(strategy)
    if not _distribution_clear(metrics=metrics, params=params):
        return False
    return True


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
