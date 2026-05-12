from __future__ import annotations

from fastapi import APIRouter, Depends

from app.agent_tools.audit import agent_audit_metrics
from app.core.admin_auth import require_admin_auth
from app.core.database import get_db
from app.core.task_manager import task_manager
from app.core.timing import request_timing_snapshot
from app.services.market.providers.circuit import provider_metrics_snapshot

router = APIRouter(prefix="/admin")


@router.get("/metrics")
def get_admin_metrics(_: None = Depends(require_admin_auth), db=Depends(get_db)) -> dict:
    snapshot = request_timing_snapshot()
    snapshot["agent_tools"] = agent_audit_metrics(db)
    snapshot["market_providers"] = provider_metrics_snapshot()
    return snapshot


@router.get("/tasks")
def get_admin_tasks(_: None = Depends(require_admin_auth)) -> dict:
    return {"items": task_manager.snapshot()}
