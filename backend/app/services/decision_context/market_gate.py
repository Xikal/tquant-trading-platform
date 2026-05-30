from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings
from app.models.schema_defs.decision_context import GateDecisionOut


MARKET_GATE_MULTIPLIER = {
    "allow": 1.0,
    "reduce": 0.62,
    "wait": 0.45,
    "research_only": 0.0,
    "block": 0.0,
    "no_data": 0.0,
}

RETREAT_STATES = {"high_flyer_retreat", "risk_release", "retreat", "weak_market", "panic"}
REPAIR_STATES = {"repair", "strong_market", "mainline_repair", "trend_up", "active"}
ROTATION_STATES = {"fast_rotation", "low_volume_wait", "neutral", "rotation", "balanced"}


@dataclass(frozen=True)
class MarketGateInput:
    market_state: str = ""
    market_state_strength: float | None = None
    limit_up_count: int | None = None
    limit_down_count: int | None = None
    turnover_amount: float | None = None
    index_trend: str = ""
    hot_sector_count: int | None = None
    previous_market_state: str = ""
    symbol_data_missing: bool = False
    data_quality: str = "ok"


def evaluate_market_gate(value: MarketGateInput) -> GateDecisionOut:
    if value.symbol_data_missing:
        return GateDecisionOut(
            decision="research_only",
            score=0.0,
            reasons=["标的数据缺失，该票仅保留研究态，不影响全局榜单。"],
            evidence={"data_quality": "missing", "effective_market_state": _effective_state(value)},
        )
    if _market_level_missing(value):
        effective_state = _effective_state(value)
        return GateDecisionOut(
            decision="reduce",
            score=62.0,
            reasons=["行情数据降级，保留上一交易日市场状态并降低生产火力。"],
            evidence={"data_quality": "degraded", "effective_market_state": effective_state},
        )

    state = _effective_state(value)
    strength = float(value.market_state_strength or 0.0)
    limit_down = int(value.limit_down_count or 0)
    limit_up = int(value.limit_up_count or 0)
    hot_sectors = int(value.hot_sector_count or 0)
    trend = str(value.index_trend or "").lower()
    evidence = {
        "data_quality": value.data_quality or "ok",
        "effective_market_state": state,
        "market_state_strength": strength,
        "limit_up_count": limit_up,
        "limit_down_count": limit_down,
        "hot_sector_count": hot_sectors,
        "index_trend": trend,
    }

    if state in RETREAT_STATES or strength < 0.35 or limit_down >= 40 or (hot_sectors <= 1 and trend == "down"):
        return GateDecisionOut(
            decision="block",
            score=max(0.0, min(35.0, strength * 100)),
            reasons=["市场处于退潮/弱势区，新开仓生产候选阻断。"],
            evidence=evidence,
        )
    if state in ROTATION_STATES or 0.35 <= strength < 0.65 or (limit_up >= 50 and trend == "down"):
        return GateDecisionOut(
            decision="reduce",
            score=max(40.0, min(68.0, strength * 100)),
            reasons=["市场处于震荡/轮动区，生产火力降级。"],
            evidence=evidence,
        )
    if state in REPAIR_STATES and strength >= 0.65 and limit_down <= 10 and hot_sectors >= 3:
        return GateDecisionOut(
            decision="allow",
            score=max(75.0, min(100.0, strength * 100)),
            reasons=["市场修复/强势，允许生产候选正常排序。"],
            evidence=evidence,
        )
    return GateDecisionOut(
        decision="reduce",
        score=max(45.0, min(72.0, strength * 100)),
        reasons=["市场证据不充分，生产火力保守降级。"],
        evidence=evidence,
    )


def market_gate_from_context(market_context) -> GateDecisionOut:  # noqa: ANN001
    if not _market_gate_enabled():
        return GateDecisionOut(
            decision="allow",
            score=100.0,
            reasons=[],
            evidence={"feature_flag_disabled": True},
        )
    return evaluate_market_gate(
        MarketGateInput(
            market_state=str(getattr(market_context, "market_state", "") or ""),
            market_state_strength=float(getattr(market_context, "market_state_strength", 0.0) or 0.0),
            limit_up_count=_int_or_none(getattr(market_context, "limit_up_count", None)),
            limit_down_count=_int_or_none(getattr(market_context, "limit_down_count", None)),
            index_trend="down" if float(getattr(market_context, "stock_median_change", 0.0) or 0.0) < 0 else "up",
            hot_sector_count=len(getattr(market_context, "hot_industries", []) or []),
            previous_market_state=str(getattr(market_context, "previous_market_state", "") or ""),
            data_quality="ok" if bool(getattr(market_context, "breadth_ready", False) or getattr(market_context, "emotion_ready", False)) else "degraded",
        )
    )


def market_gate_multiplier(decision: str) -> float:
    return MARKET_GATE_MULTIPLIER.get(str(decision or "reduce"), 0.62)


def apply_market_gate_to_score(score: float | None, gate: GateDecisionOut) -> float | None:
    if score is None:
        return None
    if gate.decision in {"block", "research_only", "no_data"}:
        return None
    return round(max(0.0, float(score) * market_gate_multiplier(gate.decision)), 2)


def _market_level_missing(value: MarketGateInput) -> bool:
    return (
        not str(value.market_state or "").strip()
        or value.market_state_strength is None
        or value.limit_up_count is None
        or value.limit_down_count is None
        or value.hot_sector_count is None
    )


def _effective_state(value: MarketGateInput) -> str:
    return str(value.market_state or value.previous_market_state or "unknown")


def _int_or_none(value) -> int | None:  # noqa: ANN001
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _market_gate_enabled() -> bool:
    settings = get_settings()
    return bool(settings.decision_context_enabled and settings.market_gate_production_enabled)
