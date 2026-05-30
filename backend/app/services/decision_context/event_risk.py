from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.schema_defs.decision_context import GateDecisionOut
from app.services.market.event_cache import load_cached_market_events


HIGH_RISK_KEYWORDS = {
    "退市": "退市风险",
    "监管处罚": "监管处罚",
    "立案": "监管处罚",
    "重大诉讼": "重大诉讼",
    "诉讼": "重大诉讼",
    "业绩暴雷": "业绩暴雷",
    "预亏": "业绩暴雷",
    "大额减持": "大额减持",
    "减持": "大额减持",
    "质押平仓": "质押平仓",
    "异常监控": "异常监控",
}
MEDIUM_RISK_KEYWORDS = {
    "问询函": "问询函",
    "问询": "问询函",
    "业绩预告": "业绩预告不确定",
    "小额减持": "小额减持",
    "重组": "重组不确定",
}
LOW_RISK_KEYWORDS = {
    "分红": "分红",
    "正常经营": "正常经营",
    "回购": "回购",
    "增持": "增持",
}


@dataclass(frozen=True)
class EventRiskInput:
    symbol: str
    trade_date: date
    events: list[dict[str, Any]]


@dataclass(frozen=True)
class EventRiskDecision:
    symbol: str
    trade_date: date
    decision: str
    severity: str
    data_quality: str
    summary: str
    risk_types: list[str]
    impact_window: str
    evidence_ids: list[str]
    reasons: list[str]
    production_blocked: bool = False

    def as_payload(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "trade_date": self.trade_date.isoformat(),
            "decision": self.decision,
            "severity": self.severity,
            "data_quality": self.data_quality,
            "summary": self.summary,
            "risk_types": list(self.risk_types),
            "impact_window": self.impact_window,
            "evidence_ids": list(self.evidence_ids),
            "reasons": list(self.reasons),
            "production_blocked": self.production_blocked,
        }


def classify_event_risk(event: dict[str, Any]) -> dict[str, Any]:
    text = f"{event.get('title') or ''} {event.get('description') or ''}"
    high = _matched_types(text, HIGH_RISK_KEYWORDS)
    if high:
        return {"severity": "high", "risk_types": high}
    medium = _matched_types(text, MEDIUM_RISK_KEYWORDS)
    if medium:
        return {"severity": "medium", "risk_types": medium}
    low = _matched_types(text, LOW_RISK_KEYWORDS)
    if low:
        return {"severity": "low", "risk_types": low}
    raw_level = str(event.get("risk_level") or "").lower()
    if raw_level in {"high", "medium", "low"}:
        return {"severity": raw_level, "risk_types": [raw_level]}
    return {"severity": "unknown", "risk_types": []}


def evaluate_event_risk_gate(value: EventRiskInput) -> EventRiskDecision:
    events = [event for event in value.events if isinstance(event, dict)]
    if not events:
        return EventRiskDecision(
            symbol=value.symbol,
            trade_date=value.trade_date,
            decision="no_data",
            severity="missing",
            data_quality="missing",
            summary="公告/事件源缺失，不能把无事件解释为安全。",
            risk_types=[],
            impact_window="unknown",
            evidence_ids=[],
            reasons=["公告/事件源缺失，事件风险只做 missing 展示，不阻断生产。"],
        )
    classified = [classify_event_risk(event) for event in events]
    severity = _max_severity(item["severity"] for item in classified)
    risk_types = _dedupe([risk_type for item in classified for risk_type in item["risk_types"]])
    evidence_ids = [
        _event_id(index, event)
        for index, event in enumerate(events, start=1)
    ]
    summary = _summary_text(events, severity, risk_types)
    if severity == "high":
        if _production_block_enabled():
            return EventRiskDecision(
                symbol=value.symbol,
                trade_date=value.trade_date,
                decision="block",
                severity=severity,
                data_quality="ok",
                summary=summary,
                risk_types=risk_types,
                impact_window="1-5 trading days",
                evidence_ids=evidence_ids,
                reasons=[f"高风险事件命中：{'、'.join(risk_types) or events[0].get('title') or '未知事件'}，生产候选阻断。"],
                production_blocked=True,
            )
        return EventRiskDecision(
            symbol=value.symbol,
            trade_date=value.trade_date,
            decision="research_only",
            severity=severity,
            data_quality="ok",
            summary=f"{summary}；生产阻断关闭，仅摘要展示。",
            risk_types=risk_types,
            impact_window="1-5 trading days",
            evidence_ids=evidence_ids,
            reasons=["高风险事件存在，但 EVENT_RISK_PRODUCTION_BLOCK_ENABLED=false，不进入生产阻断。"],
        )
    if severity == "medium":
        return EventRiskDecision(
            symbol=value.symbol,
            trade_date=value.trade_date,
            decision="reduce",
            severity=severity,
            data_quality="ok",
            summary=f"{summary}；中风险只降分告警，不阻断生产候选。",
            risk_types=risk_types,
            impact_window="1-3 trading days",
            evidence_ids=evidence_ids,
            reasons=["中风险事件触发降分并告警，不直接阻断生产。"],
        )
    return EventRiskDecision(
        symbol=value.symbol,
        trade_date=value.trade_date,
        decision="research_only",
        severity=severity,
        data_quality="ok",
        summary=summary,
        risk_types=risk_types,
        impact_window="unknown",
        evidence_ids=evidence_ids,
        reasons=["事件风险仅用于摘要展示。"],
    )


def refresh_event_risk(
    db: Session,
    *,
    symbols: list[str],
    trade_date: date,
    limit_per_symbol: int = 8,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    missing = 0
    for symbol in _clean_symbols(symbols):
        cached = load_cached_market_events(db, symbol=symbol, limit=limit_per_symbol)
        decision = evaluate_event_risk_gate(
            EventRiskInput(
                symbol=symbol,
                trade_date=trade_date,
                events=cached.events,
            )
        )
        if cached.data_quality == "missing" and decision.data_quality == "missing" and cached.reasons:
            decision = EventRiskDecision(
                symbol=decision.symbol,
                trade_date=decision.trade_date,
                decision=decision.decision,
                severity=decision.severity,
                data_quality=decision.data_quality,
                summary=decision.summary,
                risk_types=decision.risk_types,
                impact_window=decision.impact_window,
                evidence_ids=decision.evidence_ids,
                reasons=cached.reasons,
                production_blocked=False,
            )
        if decision.data_quality == "missing":
            missing += 1
        items.append(decision.as_payload())
    return {
        "ok": True,
        "worker_scope": "runtime-worker",
        "status": "ok" if len(items) > missing else "no_data",
        "gate_owner": "production-traceability-no-research-gate",
        "production_block_enabled": _production_block_enabled(),
        "trade_date": trade_date.isoformat(),
        "item_count": len(items),
        "missing_count": missing,
        "items": items,
    }


def event_risk_gate_from_candidate(candidate: Any) -> GateDecisionOut:
    raw = getattr(candidate, "event_risk_gate", None)
    if not isinstance(raw, dict):
        return GateDecisionOut(decision="allow", score=100.0, reasons=[], evidence={"source": "not_provided"})
    try:
        return GateDecisionOut.model_validate(raw)
    except Exception:
        return GateDecisionOut(decision="no_data", score=0.0, reasons=["事件风险门控格式无效。"], evidence={"data_quality": "missing"})


def apply_event_risk_gate_to_score(score: float | None, gate: GateDecisionOut) -> tuple[float | None, float]:
    if score is None:
        return None, 0.0
    if not _production_block_enabled():
        return score, 0.0
    if gate.evidence.get("source") == "not_provided":
        return score, 0.0
    if gate.decision == "block":
        return None, -float(score)
    if gate.decision == "reduce":
        penalty = _event_risk_penalty(gate)
        return round(max(0.0, float(score) + penalty), 2), penalty
    return score, 0.0


def _production_block_enabled() -> bool:
    settings = get_settings()
    return bool(settings.decision_context_enabled and settings.event_risk_production_block_enabled)


def _matched_types(text: str, mapping: dict[str, str]) -> list[str]:
    return _dedupe([risk_type for keyword, risk_type in mapping.items() if keyword in text])


def _max_severity(values) -> str:  # noqa: ANN001
    order = {"high": 3, "medium": 2, "low": 1, "unknown": 0, "missing": -1}
    result = "unknown"
    for value in values:
        key = str(value or "unknown")
        if order.get(key, 0) > order.get(result, 0):
            result = key
    return result


def _summary_text(events: list[dict[str, Any]], severity: str, risk_types: list[str]) -> str:
    first = events[0]
    title = str(first.get("title") or "事件风险")
    type_text = "、".join(risk_types) if risk_types else severity
    return f"{title}；风险类型：{type_text}；仅作为风险摘要和证据引用。"


def _event_id(index: int, event: dict[str, Any]) -> str:
    raw_id = event.get("id")
    if raw_id not in (None, ""):
        return f"market_event:{raw_id}"
    source = str(event.get("source") or "unknown")
    return f"{source}:{index}"


def _event_risk_penalty(gate: GateDecisionOut) -> float:
    severity = str(gate.evidence.get("severity") or "").lower()
    if severity == "medium":
        return -8.0
    if severity == "low":
        return -2.0
    return -5.0


def _clean_symbols(symbols: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        value = str(symbol or "").strip()
        if not value or value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result[:80]


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
