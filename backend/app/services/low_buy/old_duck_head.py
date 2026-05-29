from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.low_buy.candidate_rule_params import float_param, scoring_params
from app.services.low_buy.candidate_types import CandidateMetrics
from app.services.low_buy.shared import BoardCandidate


OLD_DUCK_HEAD_FACTOR = "old_duck_head_factor"
OLD_DUCK_HEAD_STRATEGIES = frozenset(
    {
        "n_pattern_long_wash",
        "mainline_limitup_shrink_retrace_reclaim",
        "volume_shrink",
        "leader_pullback_band",
        "ma_support",
        "ma_channel_band",
    }
)

_STRATEGY_WINDOWS = {
    "n_pattern_long_wash": (7, 15),
    "mainline_limitup_shrink_retrace_reclaim": (3, 10),
    "volume_shrink": (2, 10),
    "leader_pullback_band": (3, 12),
    "ma_support": (2, 10),
    "ma_channel_band": (3, 14),
}

_DEFAULT_CONFIG: dict[str, Any] = {
    "max_factor_score": 3.0,
    "min_volume_burst_ratio": 1.75,
    "max_post_volume_ratio": 0.9,
    "max_latest_volume_ratio": 1.15,
    "max_support_distance_pct": 2.4,
    "max_ma_reclaim_distance_pct": 1.2,
    "ma5_reclaim_ratio": 0.995,
    "min_close_position_ratio": 0.48,
    "max_distribution_risk_score": 4.8,
    "score": {
        "startup": 0.65,
        "shrink": 0.8,
        "support": 0.55,
        "reclaim": 0.55,
        "risk_clean": 0.45,
    },
}


@dataclass(frozen=True)
class OldDuckHeadAssessment:
    matched: bool
    factor_score: float = 0.0
    stage: str = "none"
    reasons: tuple[str, ...] = field(default_factory=tuple)
    failed_rules: tuple[str, ...] = field(default_factory=tuple)


def assess_old_duck_head_structure(
    strategy: str,
    item: BoardCandidate,
    metrics: CandidateMetrics,
) -> OldDuckHeadAssessment:
    """Recognize old-duck-head as a structure factor, not a standalone strategy."""

    if strategy not in OLD_DUCK_HEAD_STRATEGIES:
        return OldDuckHeadAssessment(False, failed_rules=("策略不属于老鸭头适用范围。",))

    config = _old_duck_head_config()
    min_days, max_days = _STRATEGY_WINDOWS.get(strategy, (2, 12))
    failed_rules = _failed_rules(item, metrics, config, min_days, max_days)
    if failed_rules:
        return OldDuckHeadAssessment(False, failed_rules=tuple(failed_rules))

    factor_score = _factor_score(metrics, config)
    stage = "抬头确认" if metrics.latest_close >= metrics.ma5 * float_param(config, "ma5_reclaim_ratio", 0.995) else "洗盘末端"
    reasons = (
        f"老鸭头结构：前期放量启动后缩量洗盘 {metrics.retracement_days} 天，启动低点未破，价格已进入均线承接区。",
        f"老鸭头阶段：{stage}；该信号只给相关低吸/N 字策略加分，不单独触发买入。",
    )
    return OldDuckHeadAssessment(True, factor_score=factor_score, stage=stage, reasons=reasons)


def enrich_old_duck_head_factor_scores(
    factor_scores: dict[str, float],
    assessment: OldDuckHeadAssessment,
) -> dict[str, float]:
    if not assessment.matched or assessment.factor_score <= 0:
        return factor_scores
    updated = dict(factor_scores)
    updated[OLD_DUCK_HEAD_FACTOR] = max(updated.get(OLD_DUCK_HEAD_FACTOR, 0.0), assessment.factor_score)
    return updated


def enrich_old_duck_head_payload(
    factor_scores: dict[str, float],
    reasons: list[str],
    tags: list[str],
    assessment: OldDuckHeadAssessment,
) -> tuple[dict[str, float], list[str], list[str]]:
    if not assessment.matched:
        return factor_scores, reasons, tags
    enriched_scores = enrich_old_duck_head_factor_scores(factor_scores, assessment)
    enriched_reasons = [*assessment.reasons, *reasons]
    enriched_tags = _prepend_unique("老鸭头", tags)
    return enriched_scores, enriched_reasons, enriched_tags


def _old_duck_head_config() -> dict[str, Any]:
    values = scoring_params().get("structure_factors", {}).get("old_duck_head", {})
    if not isinstance(values, dict):
        return dict(_DEFAULT_CONFIG)
    return _deep_merge(_DEFAULT_CONFIG, values)


def _failed_rules(
    item: BoardCandidate,
    metrics: CandidateMetrics,
    config: dict[str, Any],
    min_days: int,
    max_days: int,
) -> list[str]:
    failed: list[str] = []
    if not (min_days <= metrics.retracement_days <= max_days):
        failed.append(f"洗盘天数不在老鸭头窗口内：需要 {min_days}-{max_days} 天。")
    if not (metrics.board_gain_ok or metrics.volume_burst_ratio >= float_param(config, "min_volume_burst_ratio", 1.75)):
        failed.append("前期放量启动不足，不能确认主力建仓痕迹。")
    if item.board_count <= 0:
        failed.append("缺少启动板或强启动锚点。")
    if metrics.post_volume_ratio > float_param(config, "max_post_volume_ratio", 0.9):
        failed.append("洗盘期缩量不够，仍可能是普通回调。")
    if metrics.latest_volume_ratio > float_param(config, "max_latest_volume_ratio", 1.15):
        failed.append("最近量能没有维持温和修复，可能存在放量分歧。")
    if not metrics.board_low_held:
        failed.append("启动低点已失守，老鸭头结构失效。")
    if not _support_or_reclaim_ok(metrics, config):
        failed.append("价格尚未回到均线承接区或站回 5 日线附近。")
    if metrics.close_position_ratio < float_param(config, "min_close_position_ratio", 0.48):
        failed.append("收盘位置偏弱，抬头确认不足。")
    if metrics.distribution_risk_score >= float_param(config, "max_distribution_risk_score", 4.8):
        failed.append("派发风险偏高，不能按老鸭头结构加分。")
    if metrics.false_breakout_flag or metrics.stall_after_volume_flag:
        failed.append("存在假突破或放量滞涨风险。")
    if metrics.intraday_reversal_flag or metrics.long_upper_shadow or metrics.weak_close:
        failed.append("出现冲高回落、长上影或弱收盘，承接不足。")
    return failed


def _support_or_reclaim_ok(metrics: CandidateMetrics, config: dict[str, Any]) -> bool:
    max_support = float_param(config, "max_support_distance_pct", 2.4)
    max_ma_distance = float_param(config, "max_ma_reclaim_distance_pct", 1.2)
    reclaim_ratio = float_param(config, "ma5_reclaim_ratio", 0.995)
    close_to_key_ma = min(abs(metrics.close_to_ma5), abs(metrics.close_to_ma10), abs(metrics.support_distance_pct))
    return bool(
        metrics.support_ok
        or metrics.support_distance_pct <= max_support
        or close_to_key_ma <= max_ma_distance
        or (metrics.ma5 > 0 and metrics.latest_close >= metrics.ma5 * reclaim_ratio)
    )


def _factor_score(metrics: CandidateMetrics, config: dict[str, Any]) -> float:
    weights = config.get("score", {})
    weights = weights if isinstance(weights, dict) else {}
    score = 0.0
    if metrics.board_gain_ok or metrics.volume_burst_ratio >= float_param(config, "min_volume_burst_ratio", 1.75):
        score += float_param(weights, "startup", 0.65)
    if metrics.post_volume_ratio <= 0.72 and metrics.shrink_staircase:
        score += float_param(weights, "shrink", 0.8)
    elif metrics.post_volume_ratio <= float_param(config, "max_post_volume_ratio", 0.9):
        score += float_param(weights, "shrink", 0.8) * 0.65
    if metrics.board_low_held and metrics.support_distance_pct <= float_param(config, "max_support_distance_pct", 2.4):
        score += float_param(weights, "support", 0.55)
    if metrics.latest_close >= metrics.ma5 * float_param(config, "ma5_reclaim_ratio", 0.995):
        score += float_param(weights, "reclaim", 0.55)
    if metrics.distribution_risk_score <= 3.0 and not (metrics.false_breakout_flag or metrics.intraday_reversal_flag):
        score += float_param(weights, "risk_clean", 0.45)
    return round(_clamp(score, 0.0, float_param(config, "max_factor_score", 3.0)), 2)


def _deep_merge(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    result = dict(defaults)
    for key, value in overrides.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _prepend_unique(value: str, items: list[str]) -> list[str]:
    return [value, *(item for item in items if item != value)]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
