from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.admin_auth import require_admin_auth
from app.core.database import get_db
from app.services.latest_data_close_refresh import enqueue_latest_data_close_refresh
from app.services.settings_admin_snapshot import build_admin_metrics_snapshot, build_admin_task_snapshot

router = APIRouter(prefix="/admin")


@router.get("/metrics")
def get_admin_metrics(_: None = Depends(require_admin_auth), db=Depends(get_db)) -> dict:
    return build_admin_metrics_snapshot(db)


@router.post("/latest-data/refresh")
def refresh_latest_low_buy_data(_: None = Depends(require_admin_auth), db=Depends(get_db)) -> dict:
    return enqueue_latest_data_close_refresh(db)


@router.get("/tasks")
def get_admin_tasks(_: None = Depends(require_admin_auth)) -> dict:
    return build_admin_task_snapshot()
