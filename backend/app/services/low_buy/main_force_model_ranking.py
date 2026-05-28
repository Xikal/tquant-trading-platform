from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.models.schemas import LowBuyCandidateOut


def main_force_rank_bonus(candidate: LowBuyCandidateOut, *, shadow_status: dict[str, Any] | None = None) -> float:
    settings = get_settings()
    if not settings.main_force_model_enabled or not settings.main_force_model_ranking_enabled:
        return 0.0
    if not (shadow_status or {}).get("promotion_ready"):
        return 0.0
    if candidate.strategy_key not in _allowed_strategies(settings.main_force_model_allowed_strategies):
        return 0.0
    if candidate.data_quality not in {"fresh", "verified", "ok"} or candidate.risk_tier == "block":
        return 0.0
    advice = candidate.main_force_advice or {}
    if advice.get("fallback_reason"):
        return 0.0
    if advice.get("risk_flags"):
        return 0.0
    if advice.get("action") not in {"buy_probe", "buy_confirmed"}:
        return 0.0
    if advice.get("stage") not in {"washout", "markup_confirm"}:
        return 0.0
    score = _float(advice.get("score"))
    confidence = _float(advice.get("confidence"))
    min_score = float(settings.main_force_model_min_score)
    if confidence < float(settings.main_force_model_min_confidence) or score < min_score:
        return 0.0
    max_bonus = max(0.0, float(settings.main_force_model_max_rank_bonus))
    raw_bonus = (score - min_score) / max(100.0 - min_score, 1.0) * max_bonus
    multiplier = 1.0 if advice.get("action") == "buy_confirmed" else 0.65
    return round(min(max_bonus, max(0.0, raw_bonus * multiplier)), 4)


def candidate_with_main_force_rank_bonus(
    candidate: LowBuyCandidateOut,
    *,
    shadow_status: dict[str, Any] | None = None,
) -> LowBuyCandidateOut:
    bonus = main_force_rank_bonus(candidate, shadow_status=shadow_status)
    advice = dict(candidate.main_force_advice or {})
    if bonus > 0:
        advice["rank_bonus"] = bonus
        advice["production_effect"] = "ranking_bonus"
        factor_scores = dict(candidate.factor_scores or {})
        factor_scores["main_force_rank_bonus"] = bonus
        return candidate.model_copy(update={"main_force_advice": advice, "factor_scores": factor_scores})
    return candidate


def _allowed_strategies(raw: str) -> set[str]:
    return {item.strip() for item in str(raw or "").split(",") if item.strip()}


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
