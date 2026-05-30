from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import DecisionContextSnapshot
from app.models.schema_defs.decision_context import DecisionContextOut, GateDecisionOut


class DecisionContextSnapshotWriter:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert_context(self, context: DecisionContextOut, *, source_snapshot: dict[str, Any]) -> int:
        row = self.db.execute(
            select(DecisionContextSnapshot)
            .where(DecisionContextSnapshot.trade_date == context.trade_date)
            .where(DecisionContextSnapshot.strategy_key == context.strategy_key)
            .where(DecisionContextSnapshot.symbol == context.symbol)
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            row = DecisionContextSnapshot(
                trade_date=context.trade_date,
                strategy_key=context.strategy_key,
                symbol=context.symbol,
            )
            self.db.add(row)
        row.strategy_tier = context.strategy_tier
        row.production_eligible = bool(context.production_eligible)
        row.final_decision = context.final_decision
        row.final_score = float(context.final_score)
        row.data_quality = context.data_quality
        row.gates_json = _json_dumps(_gates_payload(context))
        row.evidence_json = _json_dumps(_evidence_payload(context))
        row.source_snapshot_json = _json_dumps(source_snapshot)
        self.db.commit()
        self.db.refresh(row)
        return int(row.id)

    def latest_for_symbol(self, symbol: str, *, strategy_key: str = "") -> DecisionContextOut | None:
        statement = select(DecisionContextSnapshot).where(DecisionContextSnapshot.symbol == symbol)
        if strategy_key:
            statement = statement.where(DecisionContextSnapshot.strategy_key == strategy_key)
        row = self.db.execute(
            statement.order_by(DecisionContextSnapshot.trade_date.desc(), DecisionContextSnapshot.id.desc()).limit(1)
        ).scalar_one_or_none()
        return _context_out(row) if row is not None else None

    def latest_board(self, *, trade_date: date | None = None, limit: int = 50) -> list[DecisionContextOut]:
        statement = select(DecisionContextSnapshot)
        if trade_date is None:
            latest_date = self.db.execute(select(DecisionContextSnapshot.trade_date).order_by(DecisionContextSnapshot.trade_date.desc()).limit(1)).scalar_one_or_none()
            if latest_date is None:
                return []
            trade_date = latest_date
        rows = self.db.execute(
            statement.where(DecisionContextSnapshot.trade_date == trade_date)
            .order_by(DecisionContextSnapshot.final_score.desc(), DecisionContextSnapshot.id.asc())
            .limit(max(1, int(limit or 50)))
        ).scalars().all()
        return [_context_out(row) for row in rows]


def _gates_payload(context: DecisionContextOut) -> dict[str, Any]:
    return {
        "market_gate": context.market_gate.model_dump(mode="json"),
        "sector_leader_gate": context.sector_leader_gate.model_dump(mode="json"),
        "hard_risk_gate": context.hard_risk_gate.model_dump(mode="json"),
        "event_risk_gate": context.event_risk_gate.model_dump(mode="json"),
        "intraday_entry_gate": context.intraday_entry_gate.model_dump(mode="json"),
    }


def _evidence_payload(context: DecisionContextOut) -> dict[str, Any]:
    return {
        "production_eligible": context.production_eligible,
        "strategy_tier": context.strategy_tier,
        "final_decision": context.final_decision,
        "final_score": context.final_score,
        "data_quality": context.data_quality,
    }


def _context_out(row: DecisionContextSnapshot) -> DecisionContextOut:
    gates = _json_dict(row.gates_json)
    return DecisionContextOut(
        symbol=row.symbol,
        trade_date=row.trade_date,
        strategy_key=row.strategy_key,
        strategy_tier=row.strategy_tier,  # type: ignore[arg-type]
        production_eligible=bool(row.production_eligible),
        market_gate=_gate(gates.get("market_gate"), default_decision="research_only"),
        sector_leader_gate=_gate(gates.get("sector_leader_gate"), default_decision="research_only"),
        hard_risk_gate=_gate(gates.get("hard_risk_gate"), default_decision="research_only"),
        event_risk_gate=_gate(gates.get("event_risk_gate"), default_decision="research_only"),
        intraday_entry_gate=_gate(gates.get("intraday_entry_gate"), default_decision="research_only"),
        final_decision=row.final_decision,  # type: ignore[arg-type]
        final_score=float(row.final_score or 0.0),
        data_quality=row.data_quality,  # type: ignore[arg-type]
    )


def _gate(value: Any, *, default_decision: str) -> GateDecisionOut:
    if isinstance(value, dict):
        return GateDecisionOut.model_validate(value)
    return GateDecisionOut(decision=default_decision, score=0.0, reasons=["决策上下文缺少该门控快照"])


def _json_dict(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _json_dumps(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
