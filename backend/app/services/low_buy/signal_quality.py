from __future__ import annotations

from app.services.low_buy.signal_helpers import is_hot_frontline_candidate
from app.services.low_buy.shared import LowBuyCandidateOut


def strategy_hard_buy_quality_gate(candidate: LowBuyCandidateOut) -> bool:
    if candidate.strategy_key == "first_board":
        return base_quality_clear(candidate, 5.2)
    if candidate.strategy_key == "volume_shrink":
        return (
            candidate.latest_price >= candidate.ma20 * 0.998
            and candidate.support_distance_pct <= 2.5
            and candidate.volume_shrink_ratio <= 1.08
            and base_quality_clear(candidate, 5.0)
        )
    if candidate.strategy_key == "late_session_strong_support":
        return (
            candidate.support_distance_pct <= 2.4
            and candidate.volume_shrink_ratio <= 1.08
            and is_hot_frontline_candidate(candidate)
            and base_quality_clear(candidate, 4.8)
        )
    if candidate.strategy_key == "core_midcap_vwap_ma5_retrace":
        return (
            is_hot_frontline_candidate(candidate)
            and candidate.support_distance_pct <= 1.8
            and candidate.volume_shrink_ratio <= 1.12
            and base_quality_clear(candidate, 4.8)
        )
    if candidate.strategy_key == "sector_mainline_first_divergence_low_buy":
        return (
            candidate.market_state in {"broad_rally", "repair"}
            and is_hot_frontline_candidate(candidate)
            and candidate.support_distance_pct <= 2.0
            and candidate.volume_shrink_ratio <= 1.10
            and base_quality_clear(candidate, 4.8)
        )
    if candidate.strategy_key == "mainline_limitup_shrink_retrace_reclaim":
        return (
            candidate.market_state in {"broad_rally", "repair", "low_volume_wait"}
            and is_hot_frontline_candidate(candidate)
            and candidate.latest_price >= candidate.ma5
            and candidate.support_distance_pct <= 1.9
            and candidate.volume_shrink_ratio <= 0.88
            and base_quality_clear(candidate, 4.6)
        )
    return True


def strategy_soft_buy_quality_gate(candidate: LowBuyCandidateOut) -> bool:
    if candidate.strategy_key == "first_board":
        return base_quality_clear(candidate, 5.8)
    if candidate.strategy_key == "volume_shrink":
        return (
            candidate.latest_price >= candidate.ma20 * 0.992
            and candidate.support_distance_pct <= 2.8
            and candidate.volume_shrink_ratio <= 1.15
            and base_quality_clear(candidate, 5.6)
        )
    if candidate.strategy_key == "late_session_strong_support":
        return (
            candidate.support_distance_pct <= 2.8
            and candidate.volume_shrink_ratio <= 1.15
            and is_hot_frontline_candidate(candidate)
            and base_quality_clear(candidate, 5.4)
        )
    if candidate.strategy_key == "core_midcap_vwap_ma5_retrace":
        return (
            is_hot_frontline_candidate(candidate)
            and candidate.support_distance_pct <= 2.2
            and candidate.volume_shrink_ratio <= 1.18
            and base_quality_clear(candidate, 5.2)
        )
    if candidate.strategy_key == "sector_mainline_first_divergence_low_buy":
        return (
            candidate.market_state not in {"risk_release", "high_flyer_retreat"}
            and is_hot_frontline_candidate(candidate)
            and candidate.support_distance_pct <= 2.4
            and candidate.volume_shrink_ratio <= 1.18
            and base_quality_clear(candidate, 5.2)
        )
    if candidate.strategy_key == "mainline_limitup_shrink_retrace_reclaim":
        return (
            candidate.market_state not in {"risk_release", "high_flyer_retreat"}
            and is_hot_frontline_candidate(candidate)
            and candidate.latest_price >= candidate.ma5 * 0.998
            and candidate.support_distance_pct <= 2.4
            and candidate.volume_shrink_ratio <= 0.95
            and base_quality_clear(candidate, 5.0)
        )
    return True


def base_quality_clear(candidate: LowBuyCandidateOut, distribution_limit: float) -> bool:
    return (
        candidate.distribution_risk_score < distribution_limit
        and not candidate.false_breakout_flag
        and not candidate.intraday_reversal_flag
    )


def has_distribution_hard_block(candidate: LowBuyCandidateOut) -> bool:
    if candidate.risk_tier == "block":
        return True
    if candidate.false_breakout_flag:
        if candidate.strategy_key in {"classic_retrace", "ma_support", "breakout_support"}:
            return candidate.distribution_risk_score >= 6.8
        return True
    if candidate.strategy_key in {"classic_retrace", "ma_support", "breakout_support"}:
        if candidate.distribution_risk_score >= 8.6:
            return True
        return candidate.intraday_reversal_flag and candidate.distribution_risk_score >= 7.0
    if candidate.distribution_risk_score >= 7.0:
        return True
    return candidate.intraday_reversal_flag and candidate.distribution_risk_score >= 5.0


def has_distribution_soft_block(candidate: LowBuyCandidateOut) -> bool:
    if candidate.risk_tier in {"block", "degrade"} and candidate.distribution_risk_score >= 5.5:
        return True
    if candidate.false_breakout_flag:
        if candidate.strategy_key in {"classic_retrace", "ma_support", "breakout_support"}:
            return candidate.distribution_risk_score >= 6.2
        return True
    if candidate.strategy_key in {"classic_retrace", "ma_support", "breakout_support"}:
        if candidate.distribution_risk_score >= 8.0:
            return True
        return candidate.intraday_reversal_flag and candidate.distribution_risk_score >= 6.4
    if candidate.stall_after_volume_flag and candidate.distribution_risk_score >= 5.0:
        return True
    return candidate.intraday_reversal_flag and candidate.distribution_risk_score >= 4.0
