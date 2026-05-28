from __future__ import annotations

from typing import Any

import json

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import MarketModelObservation
from app.models.schemas import LowBuyCandidateOut
from app.services.low_buy.main_force_model_schema import MAIN_FORCE_MODEL_OBSERVATION_KEY


def build_main_force_paper_advice(
    *,
    candidate: LowBuyCandidateOut | None,
    main_force_advice: dict[str, Any],
    risk_allowed: bool,
    current_position_pct: float = 0.0,
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.main_force_model_enabled or not settings.main_force_model_paper_display_enabled:
        return _hidden("paper_display_disabled")
    if not main_force_advice:
        return _hidden("main_force_advice_unavailable")
    base = {
        "visible": True,
        "mode": "readonly_shadow",
        "suggestion_enabled": False,
        "action_text": "旁路观察，不自动下单",
        "position_cap_pct": 0.0,
        "order_intent": "none",
        "stage_text": main_force_advice.get("stage_text", ""),
        "model_action_text": main_force_advice.get("action_text", ""),
        "score": _float(main_force_advice.get("score")),
        "confidence": _float(main_force_advice.get("confidence")),
        "reasons": list(main_force_advice.get("reasons") or [])[:3],
        "risk_flags": list(main_force_advice.get("risk_flags") or []),
        "production_effect": "paper_readonly_shadow",
    }
    if not settings.main_force_model_paper_suggestion_enabled:
        return base
    blocker = _suggestion_blocker(
        candidate=candidate,
        advice=main_force_advice,
        risk_allowed=risk_allowed,
        min_confidence=float(settings.main_force_model_paper_min_confidence),
    )
    if blocker:
        return {**base, "risk_flags": [*base["risk_flags"], blocker]}
    cap = max(0.0, min(float(settings.main_force_model_paper_max_position_pct), _candidate_position_cap(candidate)))
    remaining = max(0.0, cap - max(float(current_position_pct or 0.0), 0.0))
    if remaining <= 0:
        return {**base, "risk_flags": [*base["risk_flags"], "当前持仓已达到模型小仓建议上限。"]}
    return {
        **base,
        "mode": "paper_small_position_suggestion",
        "suggestion_enabled": True,
        "action_text": "模拟盘小仓观察",
        "position_cap_pct": round(remaining, 3),
        "order_intent": "manual_import_only",
        "production_effect": "paper_small_position_suggestion",
        "reasons": [
            "主力模型满足洗盘/拉升确认，且仍需手动导入和原模拟盘风控复核。",
            *base["reasons"],
        ][:3],
    }


def latest_main_force_advice_for_symbol(db: Session, symbol: str) -> dict[str, Any]:
    if not symbol:
        return {}
    row = (
        db.execute(
            select(MarketModelObservation)
            .where(
                MarketModelObservation.model_key == MAIN_FORCE_MODEL_OBSERVATION_KEY,
                MarketModelObservation.symbol == symbol,
            )
            .order_by(desc(MarketModelObservation.trade_date), desc(MarketModelObservation.id))
            .limit(1)
        )
        .scalars()
        .first()
    )
    if row is None:
        return {}
    try:
        payload = json.loads(row.payload_json or "{}")
    except Exception:
        return {}
    advice = payload.get("model_advice") if isinstance(payload, dict) else {}
    if not isinstance(advice, dict):
        return {}
    return {
        **advice,
        "shadow_trade_date": row.trade_date,
        "shadow_outcome_status": row.outcome_status,
    }


def _hidden(reason: str) -> dict[str, Any]:
    return {
        "visible": False,
        "mode": "unavailable",
        "suggestion_enabled": False,
        "action_text": "",
        "position_cap_pct": 0.0,
        "order_intent": "none",
        "reasons": [],
        "risk_flags": [reason],
        "production_effect": "none",
    }


def _suggestion_blocker(
    *,
    candidate: LowBuyCandidateOut | None,
    advice: dict[str, Any],
    risk_allowed: bool,
    min_confidence: float,
) -> str:
    if candidate is None:
        return "没有对应低吸候选，不能生成小仓建议。"
    if not risk_allowed:
        return "模拟盘风控未放行，不能生成小仓建议。"
    if candidate.buy_signal_state not in {"buy_now", "soft_buy_now", "near_entry"}:
        return "原低吸候选未到可买或接近买点。"
    if advice.get("action") not in {"buy_probe", "buy_confirmed"}:
        return "主力模型未给出小仓试买或确认买点。"
    if advice.get("stage") not in {"washout", "markup_confirm"}:
        return "主力阶段未达到洗盘/拉升确认。"
    if advice.get("risk_flags"):
        return "主力模型存在风险阻断。"
    if advice.get("fallback_reason"):
        return "主力模型 fallback，不能生成小仓建议。"
    if _float(advice.get("confidence")) < min_confidence:
        return "主力模型置信度不足。"
    if candidate.risk_tier == "block":
        return "低吸候选硬风险阻断。"
    return ""


def _candidate_position_cap(candidate: LowBuyCandidateOut | None) -> float:
    if candidate is None:
        return 0.0
    caps = [
        _float(candidate.final_position_cap_pct),
        _float(candidate.suggested_position_pct),
    ]
    positive = [item for item in caps if item > 0]
    return min(positive) if positive else 0.0


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
