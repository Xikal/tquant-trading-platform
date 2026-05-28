from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import MarketModelObservation
from app.services.market_model_observation_service import MarketModelObservationService
from app.services.paper.exit_model_schema import EXIT_MODEL_OBSERVATION_KEY, ExitModelShadowRecord


def record_exit_model_shadow(db: Session, record: ExitModelShadowRecord) -> None:
    payload = record.to_dict()
    trade_date = _trade_date(record.as_of)
    signal_state = f"{record.rule_action}->{record.model_action}"
    row = db.execute(
        select(MarketModelObservation).where(
            MarketModelObservation.model_key == EXIT_MODEL_OBSERVATION_KEY,
            MarketModelObservation.symbol == record.symbol,
            MarketModelObservation.trade_date == trade_date,
            MarketModelObservation.signal_state == signal_state,
        )
    ).scalar_one_or_none()
    payload_json = json.dumps(payload, ensure_ascii=False, default=str)
    expected_edge_pct = float(record.feature_snapshot.get("expected_return_next", 0.0) or 0.0)
    if row is None:
        db.add(
            MarketModelObservation(
                model_key=EXIT_MODEL_OBSERVATION_KEY,
                symbol=record.symbol,
                name=record.name,
                trade_date=trade_date,
                signal_state=signal_state,
                confidence=float(record.model_confidence or 0.0),
                expected_edge_pct=expected_edge_pct,
                score=float(record.model_confidence or 0.0),
                outcome_status="pending",
                payload_json=payload_json,
            )
        )
        db.flush()
        return
    row.name = record.name or row.name
    row.confidence = float(record.model_confidence or 0.0)
    row.expected_edge_pct = expected_edge_pct
    row.score = float(record.model_confidence or 0.0)
    row.payload_json = payload_json
    if row.outcome_status != "settled":
        row.outcome_status = "pending"
    db.flush()


def latest_exit_model_shadow_records(
    db: Session,
    *,
    symbol: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    statement = select(MarketModelObservation).where(MarketModelObservation.model_key == EXIT_MODEL_OBSERVATION_KEY)
    if symbol:
        statement = statement.where(MarketModelObservation.symbol == symbol)
    rows = (
        db.execute(statement.order_by(MarketModelObservation.observed_at.desc()).limit(max(1, min(limit, 500))))
        .scalars()
        .all()
    )
    return [_payload(row) for row in rows]


def summarize_exit_model_shadow(db: Session, *, lookback_days: int = 60) -> dict[str, Any]:
    summary = MarketModelObservationService().summarize(
        db,
        model_key=EXIT_MODEL_OBSERVATION_KEY,
        lookback_days=lookback_days,
    )
    rows = latest_exit_model_shadow_records(db, limit=500)
    hard_stop_records = [row for row in rows if row.get("rule_action") == "hard_stop"]
    model_fallbacks = [row for row in rows if row.get("fallback_reason")]
    sell_flying = [
        row for row in rows
        if str(row.get("model_action", "")).startswith("sell")
        and float(_nested(row, "outcome_5d", "max_favorable_5d_pct") or 0.0) >= 5.0
    ]
    return {
        **summary,
        "model_key": EXIT_MODEL_OBSERVATION_KEY,
        "hard_stop_shadow_count": len(hard_stop_records),
        "fallback_count": len(model_fallbacks),
        "fallback_rate_pct": round(len(model_fallbacks) / max(len(rows), 1) * 100.0, 3) if rows else 0.0,
        "sell_flying_count": len(sell_flying),
        "sell_flying_rate_pct": round(len(sell_flying) / max(len(rows), 1) * 100.0, 3) if rows else 0.0,
    }


def _payload(row: MarketModelObservation) -> dict[str, Any]:
    try:
        payload = json.loads(row.payload_json or "{}")
    except Exception:
        payload = {}
    payload.setdefault("symbol", row.symbol)
    payload.setdefault("name", row.name)
    payload.setdefault("model_confidence", float(row.confidence or 0.0))
    payload.setdefault("outcome_status", row.outcome_status)
    payload.setdefault("observed_at", row.observed_at.isoformat() if row.observed_at else "")
    return payload


def _trade_date(as_of: str) -> str:
    try:
        return datetime.fromisoformat(str(as_of)).date().isoformat()
    except Exception:
        return _today_key()


def _today_key() -> str:
    from app.core.timezone import beijing_today

    return beijing_today().isoformat()


def _nested(row: dict[str, Any], first: str, second: str) -> Any:
    value = row.get(first)
    return value.get(second) if isinstance(value, dict) else None
