from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_auth
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.entities import User
from app.models.schema_defs.phase4 import (
    QuantParameterAuditListResponse,
    QuantParameterExportResponse,
    QuantParameterRollbackRequest,
    QuantParameterSetCreate,
    QuantParameterSetListResponse,
    QuantParameterSetOut,
)
from app.services.quant import QuantParameterVersionService
from app.services.operation_audit import record_operation_audit

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
    market_state_scope: str = Query(default="", max_length=40),
    db: Session = Depends(get_db),
) -> QuantParameterSetOut:
    return QuantParameterVersionService(db).current(scope=scope, market_state_scope=market_state_scope)


@router.get("/export", response_model=QuantParameterExportResponse)
def export_current_quant_parameter_set(
    scope: str = Query(default="global", max_length=40),
    market_state_scope: str = Query(default="", max_length=40),
    db: Session = Depends(get_db),
) -> QuantParameterExportResponse:
    return QuantParameterVersionService(db).export_current(scope=scope, market_state_scope=market_state_scope)


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
    request: Request,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> QuantParameterSetOut:
    result = QuantParameterVersionService(db).create(payload, created_by=current_user.username)
    record_operation_audit(
        db,
        operation="quant_parameter_create",
        user=current_user,
        resource_type="quant_parameter_set",
        resource_id=result.version,
        operator_ip=_client_ip(request),
        detail={"scope": result.scope, "market_state_scope": result.market_state_scope},
    )
    db.commit()
    return result


@router.post("/rollback", response_model=QuantParameterSetOut)
def rollback_quant_parameter_set(
    payload: QuantParameterRollbackRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> QuantParameterSetOut:
    try:
        result = QuantParameterVersionService(db).rollback(payload, operator=current_user.username)
        record_operation_audit(
            db,
            operation="quant_parameter_rollback",
            user=current_user,
            resource_type="quant_parameter_set",
            resource_id=result.version,
            operator_ip=_client_ip(request),
            detail={"scope": result.scope, "market_state_scope": result.market_state_scope},
        )
        db.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else ""
