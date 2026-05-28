from __future__ import annotations

import logging
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.schemas import LowBuyCandidateOut
from app.services.low_buy.main_force_model_advisor import MainForceAdvisor
from app.services.low_buy.main_force_model_features import build_main_force_features
from app.services.low_buy.main_force_model_schema import ACTION_TEXT, STAGE_TEXT
from app.services.low_buy.main_force_model_shadow import record_main_force_shadow

logger = logging.getLogger(__name__)


def enrich_candidate_with_main_force_model(
    db: Session | None,
    *,
    candidate: LowBuyCandidateOut,
    history_rows: Iterable[Any],
    market_state: str,
    sector_strength: float,
    market_strength: float,
    record_shadow: bool = True,
) -> LowBuyCandidateOut:
    settings = get_settings()
    if not settings.main_force_model_enabled:
        return candidate
    if not settings.main_force_model_display_enabled and not settings.main_force_model_shadow_enabled:
        return candidate
    try:
        advice = _build_advice(
            candidate=candidate,
            history_rows=history_rows,
            market_state=market_state,
            sector_strength=sector_strength,
            market_strength=market_strength,
        )
    except Exception as exc:
        logger.warning("main force enrichment fallback for %s: %s", candidate.symbol, exc)
        advice = _fallback_advice(candidate, "enrichment_exception")
    enriched = candidate.model_copy(update={"main_force_advice": advice})
    if record_shadow and db is not None and settings.main_force_model_shadow_enabled:
        try:
            record_main_force_shadow(db, candidate=enriched, advice=advice, rank_bonus=_rank_bonus_from_advice(advice))
        except Exception as exc:
            logger.warning("main force shadow record failed for %s: %s", candidate.symbol, exc)
            advice = {**advice, "fallback_reason": advice.get("fallback_reason") or "shadow_record_failed"}
            enriched = enriched.model_copy(update={"main_force_advice": advice})
    return enriched


def enrich_candidates_with_main_force_model(
    db: Session | None,
    *,
    candidates: list[LowBuyCandidateOut],
    histories: dict[str, Any],
    market_state: str,
    sector_strength_by_symbol: dict[str, float] | None = None,
    market_strength: float = 0.0,
    record_shadow: bool = True,
) -> list[LowBuyCandidateOut]:
    if not candidates:
        return []
    strengths = sector_strength_by_symbol or {}
    return [
        enrich_candidate_with_main_force_model(
            db,
            candidate=candidate,
            history_rows=_history_records(histories.get(candidate.symbol)),
            market_state=market_state,
            sector_strength=strengths.get(candidate.symbol, _candidate_sector_strength(candidate)),
            market_strength=market_strength,
            record_shadow=record_shadow,
        )
        for candidate in candidates
    ]


def _build_advice(
    *,
    candidate: LowBuyCandidateOut,
    history_rows: Iterable[Any],
    market_state: str,
    sector_strength: float,
    market_strength: float,
) -> dict[str, Any]:
    features = build_main_force_features(
        history_rows,
        symbol=candidate.symbol,
        name=candidate.name,
        as_of_date=(candidate.confirmed_trade_date or candidate.quote_timestamp or "")[:10],
        strategy_key=candidate.strategy_key,
        market_state=market_state,
        sector_strength=sector_strength,
        market_strength=market_strength,
        data_quality=_feature_data_quality(candidate.data_quality),
    )
    advice = MainForceAdvisor().advise(features).to_dict()
    if features.max_source_date and features.as_of_date and features.max_source_date > features.as_of_date:
        advice.update(_fallback_advice(candidate, "future_source_date_guard"))
    if candidate.risk_tier == "block":
        advice["risk_flags"] = [*advice.get("risk_flags", []), "候选已被低吸硬风险阻断，只允许旁路观察。"]
        advice["action"] = "blocked"
        advice["action_text"] = ACTION_TEXT["blocked"]
    return advice


def _fallback_advice(candidate: LowBuyCandidateOut, reason: str) -> dict[str, Any]:
    return {
        "model": "main-force-accumulation-washout-markup-v1",
        "stage": "unavailable",
        "stage_text": STAGE_TEXT["unavailable"],
        "action": "blocked",
        "action_text": ACTION_TEXT["blocked"],
        "score": 0.0,
        "confidence": 0.0,
        "buy_zone": [],
        "stop_loss": 0.0,
        "take_profit_plan": [],
        "reasons": [],
        "risk_flags": ["主力模型暂不可用，保持原低吸策略判断。"],
        "feature_snapshot": {
            "symbol": candidate.symbol,
            "strategy_key": candidate.strategy_key,
            "as_of_date": (candidate.confirmed_trade_date or candidate.quote_timestamp or "")[:10],
            "data_quality": candidate.data_quality,
        },
        "shadow_only": True,
        "production_effect": "readonly_shadow",
        "rank_bonus": 0.0,
        "fallback_reason": reason,
    }


def _history_records(history: Any) -> list[dict[str, Any]]:
    if history is None:
        return []
    if hasattr(history, "empty") and history.empty:
        return []
    if hasattr(history, "to_dict"):
        records = history.to_dict("records")
    else:
        records = list(history)
    return [_normalize_history_row(item) for item in records]


def _normalize_history_row(row: Any) -> dict[str, Any]:
    getter = row.get if isinstance(row, dict) else lambda key, default=None: getattr(row, key, default)
    return {
        "trade_date": str(getter("trade_date", getter("date", "")) or ""),
        "open_price": getter("open_price", getter("open", 0.0)),
        "close_price": getter("close_price", getter("close", 0.0)),
        "high_price": getter("high_price", getter("high", 0.0)),
        "low_price": getter("low_price", getter("low", 0.0)),
        "volume": getter("volume", 0.0),
        "amount": getter("amount", 0.0),
        "pct_chg": getter("pct_chg", 0.0),
    }


def _feature_data_quality(value: str) -> str:
    return "fresh" if value in {"ok", "fresh", "verified"} else (value or "unavailable")


def _candidate_sector_strength(candidate: LowBuyCandidateOut) -> float:
    if candidate.mainline_tier in {"core_mainline", "secondary_mainline"}:
        return 0.72
    if candidate.industry_tier == "strong":
        return 0.65
    return 0.5


def _rank_bonus_from_advice(advice: dict[str, Any]) -> float:
    value = advice.get("rank_bonus", 0.0)
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
