from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_auth
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.schema_defs.phase4 import (
    QuantParameterAuditListResponse,
    QuantParameterExportResponse,
    QuantParameterRollbackRequest,
    QuantParameterSetCreate,
    QuantParameterSetListResponse,
    QuantParameterSetOut,
)
from app.services.quant import QuantParameterVersionService

router = APIRouter(prefix="/quant/parameters", dependencies=[Depends(get_current_user)])


@router.get("", response_model=QuantParameterSetListResponse)
def list_quant_parameter_sets(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> QuantParameterSetListResponse:
    return QuantParameterVersionService(db).list(limit=limit)


@router.get("/current", response_model=QuantParameterSetOut)
def get_current_quant_parameter_set(
    scope: str = Query(default="global", max_length=40),
    db: Session = Depends(get_db),
) -> QuantParameterSetOut:
    return QuantParameterVersionService(db).current(scope=scope)


@router.get("/export", response_model=QuantParameterExportResponse)
def export_current_quant_parameter_set(
    scope: str = Query(default="global", max_length=40),
    db: Session = Depends(get_db),
) -> QuantParameterExportResponse:
    return QuantParameterVersionService(db).export_current(scope=scope)


@router.get("/schema")
def get_quant_parameter_schema(
    db: Session = Depends(get_db),
) -> dict:
    return QuantParameterVersionService(db).schema()


@router.get("/audit", response_model=QuantParameterAuditListResponse)
def list_quant_parameter_audit(
    limit: int = Query(default=50, ge=1, le=200),
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> QuantParameterAuditListResponse:
    return QuantParameterVersionService(db).audit_logs(limit=limit)


@router.post("", response_model=QuantParameterSetOut)
def create_quant_parameter_set(
    payload: QuantParameterSetCreate,
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> QuantParameterSetOut:
    return QuantParameterVersionService(db).create(payload)


@router.post("/rollback", response_model=QuantParameterSetOut)
def rollback_quant_parameter_set(
    payload: QuantParameterRollbackRequest,
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> QuantParameterSetOut:
    try:
        return QuantParameterVersionService(db).rollback(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
