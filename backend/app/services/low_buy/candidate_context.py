from __future__ import annotations

from app.services.low_buy.candidate_types import CandidateContextAdjustment, CandidateMetrics
from app.services.low_buy.data_quality import DataQualitySnapshot
from app.services.low_buy.hard_risk import build_hard_risk_assessment
from app.services.low_buy.industry_positioning import build_industry_position_adjustment
from app.services.low_buy.dynamic_adjustments import low_buy_dynamic_adjustment
from app.services.low_buy.market_state_rules import build_low_buy_market_adjustment
from app.services.low_buy.penalty_budget import cap_candidate_score_penalty
from app.services.low_buy.risk_tiers import resolve_low_buy_risk_tier
from app.services.low_buy.shared import BoardCandidate
from app.services.low_buy.signal_family import SignalFamilyProfile
from app.services.market.regime import MarketRegimeSnapshot


def build_candidate_context_adjustment(
    *,
    strategy: str,
    item: BoardCandidate,
    metrics: CandidateMetrics,
    hot_industries: list[str],
    market_regime: MarketRegimeSnapshot | None,
    signal_profile: SignalFamilyProfile,
    factor_scores: dict[str, float],
    metrics_quality: DataQualitySnapshot | None = None,
) -> CandidateContextAdjustment:
    score_penalty = 0.0
    execution_blocked = False
    extra_risks: list[str] = []
    extra_tags: list[str] = []
    market_state_strength = 0.0
    if metrics_quality is not None and metrics_quality.quality != "ok":
        extra_tags.extend(metrics_quality.tags)
        extra_risks.append(metrics_quality.text)
        if metrics_quality.quality == "degraded":
            score_penalty += 3.0
        elif metrics_quality.quality in {"limited", "stale"}:
            score_penalty += 1.5

    if hot_industries and item.industry and item.industry not in hot_industries:
        score_penalty += 1.6
        extra_tags.append("非热点行业")
        extra_risks.append("当前不在强主线行业内，持续性通常弱于热点龙头。")
    risk_decision = resolve_low_buy_risk_tier(
        strategy=strategy,
        metrics=metrics,
        market_regime=market_regime,
    )
    hard_risk = build_hard_risk_assessment(item=item, metrics=metrics)
    score_penalty += hard_risk.score_penalty
    execution_blocked = execution_blocked or hard_risk.execution_blocked
    extra_risks.extend(hard_risk.reasons)
    extra_tags.extend(hard_risk.tags)
    score_penalty += risk_decision.score_penalty
    execution_blocked = execution_blocked or risk_decision.execution_blocked
    extra_risks.extend(risk_decision.risks)
    extra_tags.extend(risk_decision.tags)

    market_state = market_regime.state if market_regime is not None else "low_volume_wait"
    market_state_text = market_regime.label if market_regime is not None else "缩量无主线"
    dynamic_adjustment = low_buy_dynamic_adjustment(
        market_regime=market_regime,
        risk_tier=risk_decision.risk_tier,
        leader_rank=signal_profile.leader_rank,
        factor_bonuses=factor_scores,
    )
    market_adjustment = build_low_buy_market_adjustment(
        strategy=strategy,
        market_state=market_state,
        market_state_text=market_state_text,
        market_state_strength=market_regime.state_strength if market_regime is not None else 0.0,
    )
    industry_adjustment = build_industry_position_adjustment(
        sector_name=item.industry,
        hot_industries=hot_industries,
        leader_rank=signal_profile.leader_rank,
        market_state=market_state,
        market_state_strength=market_regime.state_strength if market_regime is not None else 0.0,
    )
    score_penalty += market_adjustment.score_penalty * market_adjustment.candidate_penalty_weight
    market_state_strength = market_adjustment.market_state_strength
    extra_risks.extend(market_adjustment.extra_risks)
    extra_tags.extend(
        [
            *market_adjustment.extra_tags,
            dynamic_adjustment.reason,
            industry_adjustment.label,
        ]
    )

    score_penalty, penalty_capped = cap_candidate_score_penalty(
        score_penalty=score_penalty,
        market_state=market_state,
        execution_blocked=execution_blocked,
    )
    if penalty_capped:
        extra_tags.append("风险扣分封顶")

    risk_tier = merge_risk_tier(risk_decision.risk_tier, hard_risk.level)
    return CandidateContextAdjustment(
        score_penalty=score_penalty,
        score_floor_shift=dynamic_adjustment.score_floor_shift,
        soft_buy_threshold_shift=dynamic_adjustment.soft_buy_threshold_shift,
        candidate_penalty_weight=market_adjustment.candidate_penalty_weight,
        market_position_multiplier=round(max(0.0, min(1.2, market_adjustment.position_multiplier)), 4),
        risk_position_multiplier=round(max(0.0, min(1.0, risk_decision.position_multiplier)), 4),
        dynamic_position_multiplier=dynamic_adjustment.position_multiplier,
        industry_tier=industry_adjustment.tier,
        industry_tier_text=industry_adjustment.label,
        industry_position_multiplier=industry_adjustment.multiplier,
        execution_blocked=execution_blocked,
        risk_tier=risk_tier,
        dynamic_adjustment_reason=dynamic_adjustment.reason,
        market_state=market_state,
        market_state_text=market_state_text,
        market_state_strength=market_state_strength,
        hard_risk=hard_risk,
        extra_risks=extra_risks,
        extra_tags=extra_tags,
    )


def merge_risk_tier(base_tier: str, hard_risk_level: str) -> str:
    order = {"note": 0, "degrade": 1, "block": 2}
    hard_tier = "block" if hard_risk_level == "block" else ("degrade" if hard_risk_level == "degrade" else "note")
    return hard_tier if order[hard_tier] > order.get(base_tier, 0) else base_tier
