from __future__ import annotations

from app.services.low_buy.candidate_distribution_gate import has_limit_up_distribution_exit
from app.services.low_buy.candidate_rule_params import prefilter_params
from app.services.low_buy.candidate_types import CandidateMetrics
from app.services.low_buy.shared import BoardCandidate


def passes_n_pattern_long_wash_prefilter(item: BoardCandidate, metrics: CandidateMetrics) -> bool:
    params = prefilter_params("n_pattern_long_wash")
    return (
        item.board_count <= params["max_board_count"]
        and item.amount >= params["min_amount"]
        and params["min_retracement_days"] <= metrics.retracement_days <= params["max_retracement_days"]
        and metrics.volume_burst_ratio >= params["min_volume_burst_ratio"]
        and metrics.board_low_held
        and metrics.post_volume_ratio <= params["max_post_volume_ratio"]
        and metrics.latest_volume_ratio <= params["max_latest_volume_ratio"]
        and metrics.support_distance_pct <= params["max_support_distance_pct"]
        and metrics.latest_change_pct >= params["min_latest_change_pct"]
        and metrics.close_position_ratio >= params["min_close_position_ratio"]
        and metrics.distribution_risk_score < params["max_distribution_risk_score"]
        and not metrics.false_breakout_flag
        and not metrics.intraday_reversal_flag
        and not has_limit_up_distribution_exit(metrics, params)
    )


def passes_n_pattern_short_wash_prefilter(item: BoardCandidate, metrics: CandidateMetrics) -> bool:
    params = prefilter_params("n_pattern_short_wash")
    return (
        item.board_count <= params["max_board_count"]
        and item.amount >= params["min_amount"]
        and params["min_retracement_days"] <= metrics.retracement_days <= params["max_retracement_days"]
        and metrics.volume_burst_ratio >= params["min_volume_burst_ratio"]
        and metrics.board_low_held
        and metrics.latest_volume_ratio <= params["max_latest_volume_ratio"]
        and metrics.support_distance_pct <= params["max_support_distance_pct"]
        and params["min_latest_change_pct"] <= metrics.latest_change_pct <= params["max_latest_change_pct"]
        and (metrics.doji_like or metrics.long_lower_shadow)
        and metrics.close_position_ratio >= params["min_close_position_ratio"]
        and metrics.distribution_risk_score < params["max_distribution_risk_score"]
        and not metrics.false_breakout_flag
        and not metrics.long_upper_shadow
        and not has_limit_up_distribution_exit(metrics, params)
    )
