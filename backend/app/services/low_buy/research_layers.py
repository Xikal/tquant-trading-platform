from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.low_buy.candidate_types import CandidateMetrics
from app.services.low_buy.strategy_parameter_defaults import LOW_BUY_RESEARCH_LAYER_DEFAULTS
from app.services.low_buy.shared import BoardCandidate
from app.services.quant.runtime_parameters import get_low_buy_research_layers


RESEARCH_LAYER_STRATEGIES = frozenset(
    {
        "limit_up_breakout_retrace",
        "divergence_consensus",
    }
)


@dataclass(frozen=True)
class ResearchLayerAssessment:
    stage: str
    stage_text: str
    failed_rules: list[str]
    near_miss_rules: list[str]
    blocked_reason: str = ""


def is_research_layer_strategy(strategy: str) -> bool:
    return strategy in RESEARCH_LAYER_STRATEGIES


def _research_params(strategy: str) -> dict[str, Any]:
    values = get_low_buy_research_layers()
    defaults = LOW_BUY_RESEARCH_LAYER_DEFAULTS.get(strategy, {})
    runtime = values.get(strategy, {}) if isinstance(values, dict) else {}
    return {**defaults, **runtime} if isinstance(runtime, dict) else defaults


def _hard_params() -> dict[str, Any]:
    values = get_low_buy_research_layers()
    defaults = LOW_BUY_RESEARCH_LAYER_DEFAULTS["hard_block"]
    runtime = values.get("hard_block", {}) if isinstance(values, dict) else {}
    return {**defaults, **runtime} if isinstance(runtime, dict) else defaults


def passes_research_prefilter(strategy: str, item: BoardCandidate, metrics: CandidateMetrics) -> bool:
    if strategy == "limit_up_breakout_retrace":
        return _limit_up_research_prefilter(item, metrics)
    if strategy == "divergence_consensus":
        return _divergence_research_prefilter(item, metrics)
    return False


def evaluate_research_layer(strategy: str, item: BoardCandidate, metrics: CandidateMetrics) -> ResearchLayerAssessment:
    if strategy == "limit_up_breakout_retrace":
        return _evaluate_limit_up_layer(item, metrics)
    if strategy == "divergence_consensus":
        return _evaluate_divergence_layer(item, metrics)
    return ResearchLayerAssessment(stage="none", stage_text="", failed_rules=[], near_miss_rules=[])


def _limit_up_research_prefilter(item: BoardCandidate, metrics: CandidateMetrics) -> bool:
    params = _research_params("limit_up_breakout_retrace")
    return (
        item.board_count == params["prefilter_board_count"]
        and item.amount >= params["prefilter_min_amount"]
        and metrics.board_gain_ok
        and metrics.platform_window_days >= params["prefilter_min_platform_days"]
        and params["prefilter_min_retracement_days"] <= metrics.retracement_days <= params["prefilter_max_retracement_days"]
        and metrics.volume_burst_ratio >= params["prefilter_min_volume_burst_ratio"]
        and metrics.platform_breakout_pct >= params["prefilter_min_platform_breakout_pct"]
        and metrics.platform_range_pct <= params["prefilter_max_platform_range_pct"]
        and metrics.platform_support_distance_pct <= params["prefilter_max_support_distance_pct"]
        and metrics.drawdown_from_board_pct >= params["prefilter_min_drawdown_pct"]
    )


def _divergence_research_prefilter(item: BoardCandidate, metrics: CandidateMetrics) -> bool:
    params = _research_params("divergence_consensus")
    return (
        item.board_count == params["prefilter_board_count"]
        and item.amount >= params["prefilter_min_amount"]
        and metrics.board_gain_ok
        and metrics.platform_window_days >= params["prefilter_min_platform_days"]
        and params["prefilter_min_retracement_days"] <= metrics.retracement_days <= params["prefilter_max_retracement_days"]
        and metrics.volume_burst_ratio >= params["prefilter_min_volume_burst_ratio"]
        and metrics.platform_range_pct <= params["prefilter_max_platform_range_pct"]
        and metrics.divergence_day_stall
        and metrics.consolidation_days >= params["prefilter_min_consolidation_days"]
    )


def _evaluate_limit_up_layer(item: BoardCandidate, metrics: CandidateMetrics) -> ResearchLayerAssessment:
    failed = _failed_limit_up_rules(item, metrics)
    near = _limit_up_near_misses(metrics)
    blocked = _hard_block_reason(metrics)
    if blocked:
        return ResearchLayerAssessment("blocked", "阻断", failed, near, blocked)
    if _limit_up_buy_ready(metrics):
        return ResearchLayerAssessment("buy_ready", "确认条件满足", failed, near)
    if _limit_up_near_entry(metrics):
        return ResearchLayerAssessment("near_entry", "接近买点", failed, near)
    return ResearchLayerAssessment("watch", "观察", failed, near)


def _evaluate_divergence_layer(item: BoardCandidate, metrics: CandidateMetrics) -> ResearchLayerAssessment:
    failed = _failed_divergence_rules(item, metrics)
    near = _divergence_near_misses(metrics)
    blocked = _hard_block_reason(metrics)
    if blocked:
        return ResearchLayerAssessment("blocked", "阻断", failed, near, blocked)
    if _divergence_buy_ready(metrics):
        return ResearchLayerAssessment("buy_ready", "确认条件满足", failed, near)
    if _divergence_near_entry(metrics):
        return ResearchLayerAssessment("near_entry", "接近突破", failed, near)
    return ResearchLayerAssessment("watch", "观察", failed, near)


def _hard_block_reason(metrics: CandidateMetrics) -> str:
    params = _hard_params()
    if metrics.false_breakout_flag:
        return "已经出现假突破，研究层也不继续跟踪。"
    if metrics.distribution_risk_score >= params["block_distribution_risk_score"]:
        return "派发风险过高，容易冲高回落。"
    if metrics.intraday_reversal_flag and metrics.distribution_risk_score >= params["reversal_distribution_risk_score"]:
        return "冲高回落且派发风险偏高。"
    return ""


def _limit_up_buy_ready(metrics: CandidateMetrics) -> bool:
    params = _research_params("limit_up_breakout_retrace")
    return (
        _limit_up_near_entry(metrics)
        and metrics.platform_support_distance_pct <= params["buy_max_support_distance_pct"]
        and metrics.post_volume_ratio <= params["buy_max_post_volume_ratio"]
        and metrics.latest_volume_ratio <= params["buy_max_latest_volume_ratio"]
        and metrics.latest_close >= metrics.platform_high
        and metrics.latest_close >= metrics.board_open * params["buy_min_board_open_hold_ratio"]
        and not metrics.long_upper_shadow
    )


def _limit_up_near_entry(metrics: CandidateMetrics) -> bool:
    params = _research_params("limit_up_breakout_retrace")
    return (
        metrics.platform_support_distance_pct <= params["near_max_support_distance_pct"]
        and metrics.post_volume_ratio <= params["near_max_post_volume_ratio"]
        and metrics.latest_volume_ratio <= params["near_max_latest_volume_ratio"]
        and metrics.board_low_held
        and metrics.latest_close >= metrics.platform_high * params["near_min_platform_reclaim_ratio"]
        and metrics.distribution_risk_score < params["near_max_distribution_risk_score"]
    )


def _divergence_buy_ready(metrics: CandidateMetrics) -> bool:
    params = _research_params("divergence_consensus")
    return (
        metrics.consensus_breakout
        and metrics.consolidation_volume_ratio <= params["buy_max_consolidation_volume_ratio"]
        and metrics.consensus_volume_ratio >= params["buy_min_consensus_volume_ratio"]
        and metrics.consensus_close_strength >= params["buy_min_close_strength"]
        and metrics.latest_close >= metrics.divergence_high * params["buy_min_divergence_breakout_ratio"]
        and metrics.latest_close <= metrics.divergence_high * params["buy_max_divergence_extension_ratio"]
        and metrics.distribution_risk_score < params["buy_max_distribution_risk_score"]
        and not metrics.long_upper_shadow
        and not metrics.weak_close
    )


def _divergence_near_entry(metrics: CandidateMetrics) -> bool:
    params = _research_params("divergence_consensus")
    divergence_distance_pct = abs(metrics.latest_close - metrics.divergence_high) / max(metrics.divergence_high, 0.01) * 100
    return (
        params["near_min_consolidation_days"] <= metrics.consolidation_days <= params["near_max_consolidation_days"]
        and metrics.consolidation_volume_ratio <= params["near_max_consolidation_volume_ratio"]
        and metrics.consensus_volume_ratio >= params["near_min_consensus_volume_ratio"]
        and metrics.consensus_close_strength >= params["near_min_close_strength"]
        and divergence_distance_pct <= params["near_max_divergence_distance_pct"]
        and metrics.latest_close >= metrics.consolidation_high * params["near_min_consolidation_high_reclaim_ratio"]
        and metrics.distribution_risk_score < params["near_max_distribution_risk_score"]
        and not metrics.long_upper_shadow
        and not metrics.weak_close
    )


def _failed_limit_up_rules(item: BoardCandidate, metrics: CandidateMetrics) -> list[str]:
    params = _research_params("limit_up_breakout_retrace")
    rules = [
        ("成交额不足观察阈值", item.amount >= params["failed_min_amount"]),
        ("启动放量不足", metrics.volume_burst_ratio >= params["prefilter_min_volume_burst_ratio"]),
        ("平台突破幅度不足", metrics.platform_breakout_pct >= params["prefilter_min_platform_breakout_pct"]),
        ("平台波动过大", metrics.platform_range_pct <= params["failed_max_platform_range_pct"]),
        ("距平台高点超过观察阈值", metrics.platform_support_distance_pct <= params["near_max_support_distance_pct"]),
        ("回调量能缩量不足", metrics.post_volume_ratio <= params["near_max_post_volume_ratio"]),
        ("最近一天量能仍偏大", metrics.latest_volume_ratio <= params["near_max_latest_volume_ratio"]),
        ("未守住涨停低点", metrics.board_low_held),
        ("派发风险偏高", metrics.distribution_risk_score < params["near_max_distribution_risk_score"]),
    ]
    return [label for label, passed in rules if not passed]


def _failed_divergence_rules(item: BoardCandidate, metrics: CandidateMetrics) -> list[str]:
    params = _research_params("divergence_consensus")
    rules = [
        ("成交额不足观察阈值", item.amount >= params["failed_min_amount"]),
        ("分歧日量能不足", metrics.divergence_volume_ratio >= params["failed_min_divergence_volume_ratio"]),
        ("沉淀天数不足", metrics.consolidation_days >= params["near_min_consolidation_days"]),
        ("沉淀天数过长", metrics.consolidation_days <= params["near_max_consolidation_days"]),
        ("横盘缩量不够", metrics.consolidation_volume_ratio <= params["near_max_consolidation_volume_ratio"]),
        ("还未靠近分歧高点", _distance_pct(metrics.latest_close, metrics.divergence_high) <= params["near_max_divergence_distance_pct"]),
        ("突破量能未放大", metrics.consensus_volume_ratio >= params["near_min_consensus_volume_ratio"]),
        ("收盘强度不足", metrics.consensus_close_strength >= params["near_min_close_strength"]),
        ("派发风险偏高", metrics.distribution_risk_score < params["near_max_distribution_risk_score"]),
        ("出现长上影或弱收", not metrics.long_upper_shadow and not metrics.weak_close),
    ]
    return [label for label, passed in rules if not passed]


def _limit_up_near_misses(metrics: CandidateMetrics) -> list[str]:
    params = _research_params("limit_up_breakout_retrace")
    notes: list[str] = []
    if params["near_miss_support_distance_low_pct"] < metrics.platform_support_distance_pct <= params["near_miss_support_distance_high_pct"]:
        notes.append(f"距平台高点 {metrics.platform_support_distance_pct:.1f}%，已接近但未贴近。")
    if params["near_miss_post_volume_low"] < metrics.post_volume_ratio <= params["near_miss_post_volume_high"]:
        notes.append(f"回调均量 {metrics.post_volume_ratio:.2f} 倍，缩量还不够干净。")
    if params["near_miss_drawdown_low_pct"] < metrics.drawdown_from_board_pct <= params["near_miss_drawdown_high_pct"]:
        notes.append("强势票回撤不深，可继续观察是否回踩承接。")
    return notes


def _divergence_near_misses(metrics: CandidateMetrics) -> list[str]:
    params = _research_params("divergence_consensus")
    notes: list[str] = []
    distance = _distance_pct(metrics.latest_close, metrics.divergence_high)
    if 0.0 < distance <= params["near_max_divergence_distance_pct"]:
        notes.append(f"距分歧高点约 {distance:.1f}%，接近右侧确认位。")
    if params["near_miss_volume_ratio_low"] <= metrics.consensus_volume_ratio < params["near_miss_volume_ratio_high"]:
        notes.append(f"量能回升到 {metrics.consensus_volume_ratio:.2f} 倍，但还未达到确认级别。")
    if params["near_miss_consolidation_volume_low"] < metrics.consolidation_volume_ratio <= params["near_miss_consolidation_volume_high"]:
        notes.append("横盘沉淀基本成立，但缩量还不够极致。")
    return notes


def _distance_pct(value: float, anchor: float) -> float:
    return abs(value - anchor) / max(anchor, 0.01) * 100
