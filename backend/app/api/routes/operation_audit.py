from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_auth
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.entities import OperationAuditLog
from app.models.schema_defs.operation_audit import OperationAuditListResponse, OperationAuditOut

router = APIRouter(
    prefix="/operation-audit",
    dependencies=[Depends(get_current_user), Depends(require_admin_auth)],
)


@router.get("", response_model=OperationAuditListResponse)
def list_operation_audit(
    operation: str = Query(default="", max_length=80),
    status: str = Query(default="", max_length=24),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> OperationAuditListResponse:
    statement = select(OperationAuditLog)
    total_statement = select(func.count()).select_from(OperationAuditLog)
    if operation:
        statement = statement.where(OperationAuditLog.operation == operation)
        total_statement = total_statement.where(OperationAuditLog.operation == operation)
    if status:
        statement = statement.where(OperationAuditLog.status == status)
        total_statement = total_statement.where(OperationAuditLog.status == status)
    rows = db.execute(
        statement.order_by(OperationAuditLog.id.desc()).offset(offset).limit(limit)
    ).scalars().all()
    total = int(db.execute(total_statement).scalar() or 0)
    return OperationAuditListResponse(
        items=[_out(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def _out(row: OperationAuditLog) -> OperationAuditOut:
    return OperationAuditOut(
        id=row.id,
        user_id=row.user_id,
        operation=row.operation,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        status=row.status,
        operator_ip=row.operator_ip,
        detail=_json_dict(row.detail_json),
        created_at=row.created_at,
    )


def _json_dict(raw: str) -> dict:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}
