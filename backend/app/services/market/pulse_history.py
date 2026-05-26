from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_today
from app.models.entities import MarketHourlySnapshotHistory, MarketPulseEvent
from app.models.schema_defs.market import (
    IntradayMarketPulse,
    MarketHourlySnapshotHistoryOut,
    MarketPulseEventOut,
)
from app.services.market.hourly_snapshot import hourly_all_market_snapshot_bucket


def record_hourly_snapshot_history(
    db: Session,
    payload: dict[str, Any],
    *,
    bucket: str | None = None,
) -> None:
    snapshot_bucket = bucket or hourly_all_market_snapshot_bucket()
    trade_date = _trade_date_from_bucket(snapshot_bucket, payload)
    row = db.execute(
        select(MarketHourlySnapshotHistory).where(
            MarketHourlySnapshotHistory.trade_date == trade_date,
            MarketHourlySnapshotHistory.snapshot_bucket == snapshot_bucket,
        )
    ).scalar_one_or_none()
    raw = json.dumps(payload, ensure_ascii=False, default=str)
    if row is None:
        db.add(
            MarketHourlySnapshotHistory(
                trade_date=trade_date,
                snapshot_bucket=snapshot_bucket,
                data_quality=_snapshot_quality(payload),
                snapshot_count=int(payload.get("snapshot_count") or 0),
                market_strength_score=_float(payload.get("market_strength_score")),
                payload_json=raw,
            )
        )
        return
    if _should_keep_existing_hourly(row, payload):
        return
    row.data_quality = _snapshot_quality(payload)
    row.snapshot_count = int(payload.get("snapshot_count") or 0)
    row.market_strength_score = _float(payload.get("market_strength_score"))
    row.payload_json = raw


def record_market_pulse_event(db: Session, pulse: IntradayMarketPulse) -> None:
    payload = pulse.model_dump()
    db.add(
        MarketPulseEvent(
            trade_date=_trade_date_from_timestamp(pulse.updated_at),
            pulse_level=pulse.pulse_level,
            data_quality=str(pulse.data_quality),
            pulse_text=pulse.pulse_text,
            suggested_action=pulse.suggested_action,
            payload_json=json.dumps(payload, ensure_ascii=False, default=str),
        )
    )


def list_hourly_snapshot_history(
    db: Session,
    *,
    trade_date: str = "",
    limit: int = 24,
) -> list[MarketHourlySnapshotHistoryOut]:
    statement = select(MarketHourlySnapshotHistory)
    if trade_date:
        statement = statement.where(MarketHourlySnapshotHistory.trade_date == trade_date)
    rows = db.execute(
        statement.order_by(MarketHourlySnapshotHistory.snapshot_bucket.desc()).limit(max(1, min(limit, 200)))
    ).scalars().all()
    return [_hourly_out(row) for row in rows]


def list_market_pulse_events(
    db: Session,
    *,
    trade_date: str = "",
    limit: int = 50,
) -> list[MarketPulseEventOut]:
    statement = select(MarketPulseEvent)
    if trade_date:
        statement = statement.where(MarketPulseEvent.trade_date == trade_date)
    rows = db.execute(
        statement.order_by(MarketPulseEvent.created_at.desc(), MarketPulseEvent.id.desc()).limit(max(1, min(limit, 200)))
    ).scalars().all()
    return [_pulse_out(row) for row in rows]


def _hourly_out(row: MarketHourlySnapshotHistory) -> MarketHourlySnapshotHistoryOut:
    return MarketHourlySnapshotHistoryOut(
        id=int(row.id or 0),
        trade_date=row.trade_date or "",
        snapshot_bucket=row.snapshot_bucket or "",
        data_quality=_quality(row.data_quality),
        snapshot_count=int(row.snapshot_count or 0),
        market_strength_score=_float(row.market_strength_score),
        payload=_json_dict(row.payload_json),
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


def _pulse_out(row: MarketPulseEvent) -> MarketPulseEventOut:
    return MarketPulseEventOut(
        id=int(row.id or 0),
        trade_date=row.trade_date or "",
        pulse_level=row.pulse_level or "unknown",
        data_quality=_quality(row.data_quality),
        pulse_text=row.pulse_text or "",
        suggested_action=row.suggested_action or "",
        payload=_json_dict(row.payload_json),
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


def _snapshot_quality(payload: dict[str, Any]) -> str:
    raw = str(payload.get("data_quality") or "").strip().lower()
    if raw in {"fresh", "stale", "partial", "unavailable"}:
        return raw
    return "fresh" if payload.get("ok", False) else "unavailable"


def _should_keep_existing_hourly(row: MarketHourlySnapshotHistory, payload: dict[str, Any]) -> bool:
    new_quality = _snapshot_quality(payload)
    new_count = int(payload.get("snapshot_count") or 0)
    old_quality = _quality(row.data_quality)
    old_count = int(row.snapshot_count or 0)
    return old_count > 0 and new_count <= 0 and old_quality != "unavailable" and new_quality == "unavailable"


def _trade_date_from_bucket(bucket: str, payload: dict[str, Any]) -> str:
    if len(bucket) >= 8 and bucket[:8].isdigit():
        return f"{bucket[:4]}-{bucket[4:6]}-{bucket[6:8]}"
    return _trade_date_from_timestamp(str(payload.get("updated_at") or ""))


def _trade_date_from_timestamp(value: str) -> str:
    if len(value) >= 10 and value[4] == "-" and value[7] == "-":
        return value[:10]
    return beijing_today().isoformat()


def _json_dict(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw or "{}")
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _quality(value: str) -> str:
    raw = str(value or "").strip().lower()
    return raw if raw in {"fresh", "stale", "partial", "unavailable"} else "unavailable"


def _float(value: object, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback
