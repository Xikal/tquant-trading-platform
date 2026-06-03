from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_auth
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.entities import DataQualitySnapshot, DataRepairAudit
from app.models.schema_defs.phase4 import RuntimeTaskCreate, RuntimeTaskOut
from app.services.data_quality.coverage import build_data_quality_coverage
from app.services.data_quality.schemas import (
    DataQualityBackfillRequest,
    DataQualityCoverageResponse,
    DataQualitySlaResponse,
    DataQualitySnapshotOut,
    DataRepairAuditOut,
    DataRepairRunRequest,
    RuntimeFallbackStatusResponse,
    TradeDataGateResponse,
)
from app.services.data_quality.sla import SUPPORTED_DATASETS, SUPPORTED_SCOPES
from app.services.data_quality.trade_gate import build_trade_data_gate
from app.services.market.providers import DataSourceProbeService
from app.services.runtime_worker_health import build_runtime_fallback_status
from app.services.tasks import RuntimeTaskQueue

router = APIRouter(prefix="/data-quality", dependencies=[Depends(get_current_user)])


@router.get("/sla", response_model=DataQualitySlaResponse)
def list_data_quality_sla(
    dataset_key: str | None = Query(default=None, max_length=40),
    scope: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> DataQualitySlaResponse:
    statement = select(DataQualitySnapshot)
    if dataset_key:
        statement = statement.where(DataQualitySnapshot.dataset_key == _normalize_filter(dataset_key, SUPPORTED_DATASETS))
    if scope:
        statement = statement.where(DataQualitySnapshot.scope == _normalize_filter(scope, SUPPORTED_SCOPES))
    rows = db.execute(
        statement.order_by(
            DataQualitySnapshot.as_of_date.desc(),
            DataQualitySnapshot.dataset_key.asc(),
            DataQualitySnapshot.scope.asc(),
        ).limit(limit)
    ).scalars().all()
    audits = db.execute(
        select(DataRepairAudit).order_by(DataRepairAudit.created_at.desc(), DataRepairAudit.id.desc()).limit(10)
    ).scalars().all()
    items = [_snapshot_out(row) for row in rows]
    return DataQualitySlaResponse(
        items=items,
        latest_repair_audits=[_audit_out(row) for row in audits],
        total=len(items),
    )


@router.get("/coverage", response_model=DataQualityCoverageResponse)
def get_data_quality_coverage(
    dataset_key: str = Query(default="daily_bars", max_length=40),
    scope: str = Query(default="all", max_length=40),
    db: Session = Depends(get_db),
) -> DataQualityCoverageResponse:
    try:
        return build_data_quality_coverage(db, dataset_key=dataset_key, scope=scope)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/backfill", response_model=RuntimeTaskOut)
def enqueue_data_quality_backfill(
    payload: DataQualityBackfillRequest,
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> RuntimeTaskOut:
    dataset_key = _normalize_filter(payload.dataset_key, SUPPORTED_DATASETS)
    scope = _normalize_filter(payload.scope, SUPPORTED_SCOPES)
    if payload.start_date > payload.end_date:
        raise HTTPException(status_code=400, detail="start_date must be <= end_date")
    task_payload = {
        "dataset_key": dataset_key,
        "scope": scope,
        "start_date": payload.start_date.isoformat(),
        "end_date": payload.end_date.isoformat(),
    }
    return RuntimeTaskQueue(db).enqueue(
        RuntimeTaskCreate(
            task_type="data_quality_backfill",
            payload=task_payload,
            priority=25,
            idempotency_key=f"data_quality_backfill:{dataset_key}:{scope}:{payload.start_date}:{payload.end_date}",
            max_attempts=2,
        )
    )


@router.get("/trade-gate", response_model=TradeDataGateResponse)
def get_trade_data_gate(db: Session = Depends(get_db)) -> TradeDataGateResponse:
    try:
        source_probe = DataSourceProbeService().probe()
    except Exception:
        source_probe = None
    return build_trade_data_gate(db, source_probe=source_probe)


@router.get("/runtime-fallback", response_model=RuntimeFallbackStatusResponse)
def get_runtime_fallback_status(db: Session = Depends(get_db)) -> RuntimeFallbackStatusResponse:
    return RuntimeFallbackStatusResponse(**build_runtime_fallback_status(db))


@router.post("/repair", response_model=RuntimeTaskOut)
def enqueue_data_repair(
    payload: DataRepairRunRequest,
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> RuntimeTaskOut:
    dataset_key = _normalize_filter(payload.dataset_key, SUPPORTED_DATASETS)
    dry_run = bool(payload.dry_run)
    task_payload = {
        "dataset_key": dataset_key,
        "dry_run": dry_run,
        "refetch": bool(payload.refetch),
    }
    if payload.output_path.strip():
        task_payload["output_path"] = payload.output_path.strip()
    if payload.backup_dir.strip():
        task_payload["backup_dir"] = payload.backup_dir.strip()
    idempotency_key = f"data_repair_run:{dataset_key}:{'dry_run' if dry_run else 'apply'}:{date.today().isoformat()}"
    return RuntimeTaskQueue(db).enqueue(
        RuntimeTaskCreate(
            task_type="data_repair_run",
            payload=task_payload,
            priority=30,
            idempotency_key=idempotency_key,
            max_attempts=1 if not dry_run else 3,
        )
    )


def _snapshot_out(row: DataQualitySnapshot) -> DataQualitySnapshotOut:
    return DataQualitySnapshotOut(
        dataset_key=row.dataset_key,
        as_of_date=row.as_of_date,
        scope=row.scope,
        expected_days=int(row.expected_days or 0),
        actual_days=int(row.actual_days or 0),
        missing_days=int(row.missing_days or 0),
        invalid_rows=int(row.invalid_rows or 0),
        duplicate_rows=int(row.duplicate_rows or 0),
        stale=bool(row.stale),
        coverage_pct=float(row.coverage_pct or 0.0),
        status=row.status,
        blockers=_json_list(row.blockers_json),
        checked_at=row.checked_at,
    )


def _audit_out(row: DataRepairAudit) -> DataRepairAuditOut:
    return DataRepairAuditOut(
        id=int(row.id or 0),
        repair_id=row.repair_id,
        dataset_key=row.dataset_key,
        reason=row.reason,
        backup_path=row.backup_path or "",
        refetch_result=row.refetch_result or "",
        deleted_rows_count=len(_json_list(row.deleted_rows_json)),
        fabricated=bool(row.fabricated),
        operator=row.operator or "",
        created_at=row.created_at,
    )


def _json_list(value: str | None) -> list:
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return []
    return loaded if isinstance(loaded, list) else []


def _normalize_filter(value: str, allowed: set[str]) -> str:
    normalized = value.strip()
    if normalized not in allowed:
        raise HTTPException(status_code=400, detail=f"unsupported data quality filter: {value}")
    return normalized
