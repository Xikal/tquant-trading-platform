from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import DataQualitySnapshot, DataRepairAudit


def data_quality_sla_payload(db: Session, *, limit: int = 50, audit_limit: int = 10) -> dict[str, Any]:
    snapshots = db.execute(
        select(DataQualitySnapshot)
        .order_by(
            DataQualitySnapshot.as_of_date.desc(),
            DataQualitySnapshot.dataset_key.asc(),
            DataQualitySnapshot.scope.asc(),
        )
        .limit(limit)
    ).scalars().all()
    audits = db.execute(
        select(DataRepairAudit).order_by(DataRepairAudit.created_at.desc(), DataRepairAudit.id.desc()).limit(audit_limit)
    ).scalars().all()
    return {
        "items": [_snapshot_dict(row) for row in snapshots],
        "latest_repair_audits": [_audit_dict(row) for row in audits],
    }


def _snapshot_dict(row: DataQualitySnapshot) -> dict[str, Any]:
    return {
        "dataset_key": row.dataset_key,
        "as_of_date": row.as_of_date.isoformat() if row.as_of_date else "",
        "scope": row.scope,
        "expected_days": int(row.expected_days or 0),
        "actual_days": int(row.actual_days or 0),
        "missing_days": int(row.missing_days or 0),
        "invalid_rows": int(row.invalid_rows or 0),
        "duplicate_rows": int(row.duplicate_rows or 0),
        "stale": bool(row.stale),
        "coverage_pct": float(row.coverage_pct or 0.0),
        "status": row.status,
        "blockers": _json_list(row.blockers_json),
        "checked_at": row.checked_at.isoformat() if row.checked_at else "",
    }


def _audit_dict(row: DataRepairAudit) -> dict[str, Any]:
    return {
        "id": int(row.id or 0),
        "repair_id": row.repair_id,
        "dataset_key": row.dataset_key,
        "reason": row.reason,
        "backup_path": row.backup_path or "",
        "refetch_result": row.refetch_result or "",
        "deleted_rows_count": len(_json_list(row.deleted_rows_json)),
        "fabricated": bool(row.fabricated),
        "operator": row.operator or "",
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


def _json_list(value: str | None) -> list[Any]:
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return []
    return loaded if isinstance(loaded, list) else []
