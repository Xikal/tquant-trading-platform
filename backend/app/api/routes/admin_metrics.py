from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.admin_auth import require_admin_auth
from app.core.timing import request_timing_snapshot

router = APIRouter(prefix="/admin")


@router.get("/metrics")
def get_admin_metrics(_: None = Depends(require_admin_auth)) -> dict:
    return request_timing_snapshot()
