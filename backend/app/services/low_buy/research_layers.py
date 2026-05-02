from __future__ import annotations

from dataclasses import dataclass

from app.services.low_buy.candidate_types import CandidateMetrics
from app.services.low_buy.shared import BoardCandidate


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
    return (
        item.board_count == 1
        and item.amount >= 100_000_000
        and metrics.board_gain_ok
        and metrics.platform_window_days >= 20
        and 1 <= metrics.retracement_days <= 8
        and metrics.volume_burst_ratio >= 1.5
        and metrics.platform_breakout_pct >= 0.0
        and metrics.platform_range_pct <= 50.0
        and metrics.platform_support_distance_pct <= 10.0
        and metrics.drawdown_from_board_pct >= -12.0
    )


def _divergence_research_prefilter(item: BoardCandidate, metrics: CandidateMetrics) -> bool:
    return (
        item.board_count == 1
        and item.amount >= 120_000_000
        and metrics.board_gain_ok
        and metrics.platform_window_days >= 20
        and 2 <= metrics.retracement_days <= 10
        and metrics.volume_burst_ratio >= 1.5
        and metrics.platform_range_pct <= 50.0
        and metrics.divergence_day_stall
        and metrics.consolidation_days >= 1
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
    if metrics.false_breakout_flag:
        return "已经出现假突破，研究层也不继续跟踪。"
    if metrics.distribution_risk_score >= 7.0:
        return "派发风险过高，容易冲高回落。"
    if metrics.intraday_reversal_flag and metrics.distribution_risk_score >= 5.0:
        return "冲高回落且派发风险偏高。"
    return ""


def _limit_up_buy_ready(metrics: CandidateMetrics) -> bool:
    return (
        _limit_up_near_entry(metrics)
        and metrics.platform_support_distance_pct <= 2.0
        and metrics.post_volume_ratio <= 0.72
        and metrics.latest_volume_ratio <= 0.80
        and metrics.latest_close >= metrics.platform_high
        and metrics.latest_close >= metrics.board_open * 0.985
        and not metrics.long_upper_shadow
    )


def _limit_up_near_entry(metrics: CandidateMetrics) -> bool:
    return (
        metrics.platform_support_distance_pct <= 4.0
        and metrics.post_volume_ratio <= 0.90
        and metrics.latest_volume_ratio <= 0.95
        and metrics.board_low_held
        and metrics.latest_close >= metrics.platform_high * 0.985
        and metrics.distribution_risk_score < 5.8
    )


def _divergence_buy_ready(metrics: CandidateMetrics) -> bool:
    return (
        metrics.consensus_breakout
        and metrics.consolidation_volume_ratio <= 0.65
        and metrics.consensus_volume_ratio >= 1.60
        and metrics.consensus_close_strength >= 0.65
        and metrics.latest_close >= metrics.divergence_high * 1.01
        and metrics.latest_close <= metrics.divergence_high * 1.05
        and metrics.distribution_risk_score < 4.5
        and not metrics.long_upper_shadow
        and not metrics.weak_close
    )


def _divergence_near_entry(metrics: CandidateMetrics) -> bool:
    divergence_distance_pct = abs(metrics.latest_close - metrics.divergence_high) / max(metrics.divergence_high, 0.01) * 100
    return (
        2 <= metrics.consolidation_days <= 6
        and metrics.consolidation_volume_ratio <= 0.75
        and metrics.consensus_volume_ratio >= 1.35
        and metrics.consensus_close_strength >= 0.45
        and divergence_distance_pct <= 3.0
        and metrics.latest_close >= metrics.consolidation_high * 0.985
        and metrics.distribution_risk_score < 5.5
        and not metrics.long_upper_shadow
        and not metrics.weak_close
    )


def _failed_limit_up_rules(item: BoardCandidate, metrics: CandidateMetrics) -> list[str]:
    rules = [
        ("成交额不足 1.5 亿", item.amount >= 150_000_000),
        ("启动放量不足 1.5 倍", metrics.volume_burst_ratio >= 1.5),
        ("平台突破幅度不足", metrics.platform_breakout_pct >= 0.0),
        ("平台波动过大", metrics.platform_range_pct <= 40.0),
        ("距平台高点超过 4%", metrics.platform_support_distance_pct <= 4.0),
        ("回调量能未缩到 0.90 倍以内", metrics.post_volume_ratio <= 0.90),
        ("最近一天量能仍偏大", metrics.latest_volume_ratio <= 0.95),
        ("未守住涨停低点", metrics.board_low_held),
        ("派发风险偏高", metrics.distribution_risk_score < 5.8),
    ]
    return [label for label, passed in rules if not passed]


def _failed_divergence_rules(item: BoardCandidate, metrics: CandidateMetrics) -> list[str]:
    rules = [
        ("成交额不足 1.8 亿", item.amount >= 180_000_000),
        ("分歧日量能不足", metrics.divergence_volume_ratio >= 0.55),
        ("沉淀天数不足", metrics.consolidation_days >= 2),
        ("沉淀天数过长", metrics.consolidation_days <= 6),
        ("横盘缩量不够", metrics.consolidation_volume_ratio <= 0.75),
        ("还未靠近分歧高点", _distance_pct(metrics.latest_close, metrics.divergence_high) <= 3.0),
        ("突破量能未放大", metrics.consensus_volume_ratio >= 1.35),
        ("收盘强度不足", metrics.consensus_close_strength >= 0.45),
        ("派发风险偏高", metrics.distribution_risk_score < 5.5),
        ("出现长上影或弱收", not metrics.long_upper_shadow and not metrics.weak_close),
    ]
    return [label for label, passed in rules if not passed]


def _limit_up_near_misses(metrics: CandidateMetrics) -> list[str]:
    notes: list[str] = []
    if 2.0 < metrics.platform_support_distance_pct <= 4.0:
        notes.append(f"距平台高点 {metrics.platform_support_distance_pct:.1f}%，已接近但未贴近。")
    if 0.72 < metrics.post_volume_ratio <= 0.90:
        notes.append(f"回调均量 {metrics.post_volume_ratio:.2f} 倍，缩量还不够干净。")
    if -3.0 < metrics.drawdown_from_board_pct <= 3.0:
        notes.append("强势票回撤不深，可继续观察是否回踩承接。")
    return notes


def _divergence_near_misses(metrics: CandidateMetrics) -> list[str]:
    notes: list[str] = []
    distance = _distance_pct(metrics.latest_close, metrics.divergence_high)
    if 0.0 < distance <= 3.0:
        notes.append(f"距分歧高点约 {distance:.1f}%，接近右侧确认位。")
    if 1.35 <= metrics.consensus_volume_ratio < 1.60:
        notes.append(f"量能回升到 {metrics.consensus_volume_ratio:.2f} 倍，但还未达到确认级别。")
    if 0.65 < metrics.consolidation_volume_ratio <= 0.75:
        notes.append("横盘沉淀基本成立，但缩量还不够极致。")
    return notes


def _distance_pct(value: float, anchor: float) -> float:
    return abs(value - anchor) / max(anchor, 0.01) * 100
