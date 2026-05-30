from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import StrategyPromotionReview
from app.services.low_buy.strategy_policy import get_strategy_tier


@dataclass(frozen=True)
class PromotionEvidence:
    strategy_key: str
    review_date: date
    window_days: int = 504
    sample_count: int = 0
    profit_factor: float = 0.0
    average_trade_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    max5_return_pct: float = 0.0
    max10_return_pct: float = 0.0
    quarterly_stability: float = 0.0
    walk_forward_pass: bool = False
    oos_pass: bool = False
    recent_quarter_returns_pct: tuple[float, ...] = field(default_factory=tuple)
    source: str = "decision_context_promotion_engine"


@dataclass(frozen=True)
class PromotionReviewResult:
    strategy_key: str
    current_tier: str
    recommended_tier: str
    recommendation: str
    evidence: dict[str, Any]
    blocking_reasons: list[str]
    can_apply_override: bool = False

    def as_payload(self) -> dict[str, Any]:
        return {
            "strategy_key": self.strategy_key,
            "current_tier": self.current_tier,
            "recommended_tier": self.recommended_tier,
            "recommendation": self.recommendation,
            "evidence": dict(self.evidence),
            "blocking_reasons": list(self.blocking_reasons),
            "can_apply_override": False,
        }


def review_strategy_promotion(db: Session, evidence: PromotionEvidence) -> PromotionReviewResult:
    current_tier = get_strategy_tier(evidence.strategy_key).value
    recommendation, recommended_tier, blocking_reasons = _recommendation(evidence)
    result = PromotionReviewResult(
        strategy_key=evidence.strategy_key,
        current_tier=current_tier,
        recommended_tier=recommended_tier,
        recommendation=recommendation,
        evidence=_evidence_payload(evidence),
        blocking_reasons=blocking_reasons,
        can_apply_override=False,
    )
    _upsert_review(db, evidence, result)
    return result


def _recommendation(evidence: PromotionEvidence) -> tuple[str, str, list[str]]:
    aux_blockers = _aux_blockers(evidence)
    core_blockers = _core_blockers(evidence)
    if not core_blockers:
        return "promote_to_core_review", "core", []
    if not aux_blockers:
        return "promote_to_auxiliary_review", "auxiliary", []
    return "stay_research", get_strategy_tier(evidence.strategy_key).value, aux_blockers


def _aux_blockers(evidence: PromotionEvidence) -> list[str]:
    blockers: list[str] = []
    if evidence.sample_count < 200:
        blockers.append("sample_count < 200")
    if evidence.profit_factor < 1.20:
        blockers.append("PF < 1.20")
    if evidence.average_trade_pct <= 0:
        blockers.append("average_trade <= 0")
    if evidence.max_drawdown_pct < -12.0:
        blockers.append("max_drawdown < -12%")
    if evidence.quarterly_stability < 0.60:
        blockers.append("quarterly_stability < 0.60")
    if not evidence.walk_forward_pass:
        blockers.append("walk-forward 未通过")
    if not evidence.oos_pass:
        blockers.append("OOS 未通过")
    return blockers


def _core_blockers(evidence: PromotionEvidence) -> list[str]:
    blockers: list[str] = []
    if evidence.sample_count < 500:
        blockers.append("sample_count < 500")
    if evidence.profit_factor < 1.35:
        blockers.append("PF < 1.35")
    if evidence.average_trade_pct < 0.45:
        blockers.append("average_trade < 0.45")
    if evidence.max_drawdown_pct < -10.0:
        blockers.append("max_drawdown < -10%")
    if evidence.max5_return_pct <= 0 or evidence.max10_return_pct <= 0:
        blockers.append("max5/max10 真实组合收益未同时为正")
    if evidence.quarterly_stability < 0.70:
        blockers.append("quarterly_stability < 0.70")
    if not evidence.walk_forward_pass:
        blockers.append("walk-forward 未通过")
    if not evidence.oos_pass:
        blockers.append("OOS 未通过")
    recent = tuple(evidence.recent_quarter_returns_pct or ())
    if len(recent) >= 2 and recent[-1] < 0 and recent[-2] < 0:
        blockers.append("最近两季同时为负")
    return blockers


def _upsert_review(db: Session, evidence: PromotionEvidence, result: PromotionReviewResult) -> None:
    row = db.execute(
        select(StrategyPromotionReview).where(
            StrategyPromotionReview.strategy_key == evidence.strategy_key,
            StrategyPromotionReview.review_date == evidence.review_date,
            StrategyPromotionReview.window_days == evidence.window_days,
        )
    ).scalar_one_or_none()
    if row is None:
        row = StrategyPromotionReview(
            strategy_key=evidence.strategy_key,
            review_date=evidence.review_date,
            window_days=evidence.window_days,
        )
        db.add(row)
    row.sample_count = int(evidence.sample_count)
    row.profit_factor = float(evidence.profit_factor)
    row.average_trade_pct = float(evidence.average_trade_pct)
    row.max_drawdown_pct = float(evidence.max_drawdown_pct)
    row.max5_return_pct = float(evidence.max5_return_pct)
    row.max10_return_pct = float(evidence.max10_return_pct)
    row.quarterly_stability = float(evidence.quarterly_stability)
    row.walk_forward_pass = bool(evidence.walk_forward_pass)
    row.oos_pass = bool(evidence.oos_pass)
    row.recommendation = result.recommendation
    row.evidence_json = json.dumps(result.as_payload(), ensure_ascii=False, sort_keys=True)
    db.commit()


def _evidence_payload(evidence: PromotionEvidence) -> dict[str, Any]:
    return {
        "sample_count": int(evidence.sample_count),
        "profit_factor": float(evidence.profit_factor),
        "average_trade_pct": float(evidence.average_trade_pct),
        "max_drawdown_pct": float(evidence.max_drawdown_pct),
        "max5_return_pct": float(evidence.max5_return_pct),
        "max10_return_pct": float(evidence.max10_return_pct),
        "quarterly_stability": float(evidence.quarterly_stability),
        "walk_forward_pass": bool(evidence.walk_forward_pass),
        "oos_pass": bool(evidence.oos_pass),
        "recent_quarter_returns_pct": list(evidence.recent_quarter_returns_pct or ()),
        "source": evidence.source,
        "auto_apply_enabled": bool(get_settings().promotion_engine_auto_apply_enabled),
    }
