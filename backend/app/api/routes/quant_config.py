from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_auth
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.schema_defs.phase4 import (
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


@router.post("", response_model=QuantParameterSetOut)
def create_quant_parameter_set(
    payload: QuantParameterSetCreate,
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> QuantParameterSetOut:
    return QuantParameterVersionService(db).create(payload)
