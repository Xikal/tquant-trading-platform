from __future__ import annotations

from app.services.low_buy.candidate_types import CandidateMetrics
from app.services.low_buy.shared import LOW_BUY_THRESHOLDS


def evaluate_selection_quality_factor(metrics: CandidateMetrics) -> float:
    """Score non-breaking stock-picking quality signals.

    This factor does not gate candidates. It only rewards cleaner A-share
    low-buy structures: volume contraction, meaningful pullback, prior impulse,
    and lower distribution risk.
    """

    score = 0.0
    if _has_continuous_volume_contraction(metrics):
        score += 1.2
    if _has_meaningful_ma20_pullback(metrics):
        score += 0.8
    if _has_recent_impulse(metrics):
        score += 0.6
    if _has_low_distribution_risk(metrics):
        score += 0.5
    if metrics.false_breakout_flag or metrics.stall_after_volume_flag:
        score -= 1.0
    return round(_clamp(score, 0.0, 3.0), 2)


def _has_continuous_volume_contraction(metrics: CandidateMetrics) -> bool:
    volume_max = float(LOW_BUY_THRESHOLDS.SELECTION_QUALITY_VOLUME_MAX)
    return bool(
        metrics.shrink_staircase
        and metrics.post_volume_ratio <= volume_max
        and metrics.latest_volume_ratio <= max(volume_max, 0.95)
    )


def _has_meaningful_ma20_pullback(metrics: CandidateMetrics) -> bool:
    distance_min = float(LOW_BUY_THRESHOLDS.SELECTION_QUALITY_MA20_DISTANCE_MIN)
    distance_max = float(LOW_BUY_THRESHOLDS.SELECTION_QUALITY_MA20_DISTANCE_MAX)
    if metrics.ma20 <= 0:
        return False
    signed_distance = (metrics.latest_close - metrics.ma20) / max(metrics.ma20, 0.01) * 100
    return -distance_max <= signed_distance <= -distance_min


def _has_recent_impulse(metrics: CandidateMetrics) -> bool:
    min_burst = float(LOW_BUY_THRESHOLDS.SELECTION_QUALITY_VOLUME_BURST_MIN)
    return bool(metrics.board_gain_ok or metrics.volume_burst_ratio >= min_burst)


def _has_low_distribution_risk(metrics: CandidateMetrics) -> bool:
    max_risk = float(LOW_BUY_THRESHOLDS.SELECTION_QUALITY_DISTRIBUTION_RISK_MAX)
    return metrics.distribution_risk_score <= max_risk


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
