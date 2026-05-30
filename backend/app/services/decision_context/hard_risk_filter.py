from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import get_settings
from app.models.schema_defs.decision_context import GateDecisionOut


@dataclass(frozen=True)
class HardRiskInput:
    symbol: str
    name: str = ""
    is_st: bool = False
    status: str = "active"
    data_quality: str = "missing"
    source: str = ""
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    close_price: float | None = None
    current_price: float | None = None
    volume: float | None = None
    amount: float | None = None
    is_suspended: bool = False
    up_limit: float | None = None
    down_limit: float | None = None
    event_risk_severity: str = ""
    listing_age_days: int | None = None
    gap_pct: float | None = None
    metadata_stale: bool = False
    reasons: list[str] = field(default_factory=list)


def evaluate_hard_risk_gate(value: HardRiskInput) -> GateDecisionOut:
    reasons = list(value.reasons)
    reduce_reasons: list[str] = []
    evidence = {
        "symbol": value.symbol,
        "status": value.status,
        "data_quality": value.data_quality,
        "source": value.source,
    }
    name_upper = str(value.name or "").upper()
    if value.is_st or "ST" in name_upper or "退" in str(value.name or ""):
        reasons.append("ST/退市风险标记，生产候选阻断。")
    if value.status and value.status != "active":
        reasons.append(f"标的状态为 {value.status}，生产候选阻断。")
    if value.is_suspended:
        reasons.append("标的疑似停牌，无法假定成交。")
    if str(value.data_quality or "").lower() in {"invalid_ohlc", "blocked"}:
        reasons.append("OHLC 数据异常，无法生成生产分。")
    if _invalid_ohlc(value):
        reasons.append("OHLC 价格关系不合法，无法生成生产分。")
        evidence["data_quality"] = "invalid_ohlc"
    if value.event_risk_severity == "high":
        reasons.append("高风险事件命中，生产候选阻断。")
    if value.listing_age_days is not None and value.listing_age_days < 20:
        reasons.append("上市时间过短，暂不进入生产候选。")
    if value.volume is not None and value.volume <= 0:
        reasons.append("成交量为 0，疑似不可交易。")
    if value.amount is not None and value.amount <= 0:
        reasons.append("成交额缺失或为 0，疑似不可交易。")

    price = value.current_price if value.current_price is not None else value.close_price
    if price is not None and value.up_limit is not None and price >= value.up_limit:
        reasons.append("买入价格触及涨停，不能假定可成交。")
    if price is not None and value.down_limit is not None and price <= value.down_limit:
        reasons.append("价格触及跌停，卖出流动性需显式处理。")
    if price is not None and (value.up_limit is None or value.down_limit is None):
        reduce_reasons.append("缺少涨跌停元数据，生产分降权。")
    if value.gap_pct is not None and value.gap_pct >= 7.0:
        reduce_reasons.append("跳空过高，避免追高，生产分降权。")
    if value.metadata_stale:
        reduce_reasons.append("标的或板块元数据陈旧，生产分降权。")

    if reasons:
        return GateDecisionOut(decision="block", score=0.0, reasons=_dedupe(reasons), evidence=evidence)
    if reduce_reasons:
        return GateDecisionOut(decision="reduce", score=62.0, reasons=_dedupe(reduce_reasons), evidence=evidence)
    return GateDecisionOut(decision="allow", score=100.0, reasons=[], evidence=evidence)


def hard_risk_gate_from_snapshot(snapshot: dict | None) -> GateDecisionOut:
    if not _hard_risk_filter_enabled():
        return GateDecisionOut(
            decision="allow",
            score=100.0,
            reasons=[],
            evidence={"feature_flag_disabled": True},
        )
    value = snapshot if isinstance(snapshot, dict) else {}
    raw_gate = value.get("hard_risk_gate") or value.get("hard_risk")
    if isinstance(raw_gate, dict):
        decision = str(raw_gate.get("decision") or raw_gate.get("level") or "").strip()
        if decision in {"allow", "reduce", "block", "wait", "research_only", "no_data"}:
            return GateDecisionOut(
                decision=decision,  # type: ignore[arg-type]
                score=float(raw_gate.get("score") if raw_gate.get("score") is not None else (0.0 if decision == "block" else 100.0)),
                reasons=[str(item) for item in raw_gate.get("reasons") or []],
                evidence=raw_gate.get("evidence") if isinstance(raw_gate.get("evidence"), dict) else {},
            )
    return GateDecisionOut(decision="allow", score=100.0, reasons=[], evidence={})


def mark_manual_hard_risk_override(snapshot: dict, gate: GateDecisionOut) -> dict:
    updated = dict(snapshot or {})
    updated["risk_override_required"] = True
    updated["risk_override_reason"] = "；".join(gate.reasons) or "硬风控阻断，手动单需复核。"
    updated["hard_risk_gate"] = gate.model_dump(mode="json")
    return updated


def _invalid_ohlc(value: HardRiskInput) -> bool:
    open_price = value.open_price
    high_price = value.high_price
    low_price = value.low_price
    close_price = value.close_price
    prices = [item for item in (open_price, high_price, low_price, close_price) if item is not None]
    if any(float(item) <= 0 for item in prices):
        return True
    if high_price is not None and low_price is not None and high_price < low_price:
        return True
    if high_price is not None and open_price is not None and high_price < open_price:
        return True
    if high_price is not None and close_price is not None and high_price < close_price:
        return True
    if low_price is not None and open_price is not None and low_price > open_price:
        return True
    if low_price is not None and close_price is not None and low_price > close_price:
        return True
    return False


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _hard_risk_filter_enabled() -> bool:
    settings = get_settings()
    return bool(settings.decision_context_enabled and settings.hard_risk_filter_production_enabled)
