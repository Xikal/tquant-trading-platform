from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.entities import User
from app.models.schema_defs.monitor import MonitorSnapshotResponse
from app.services.monitor_snapshot_service import build_monitor_snapshot

router = APIRouter(prefix="/monitor", dependencies=[Depends(get_current_user)])


@router.get("/snapshot", response_model=MonitorSnapshotResponse)
def monitor_snapshot(
    priority_limit: int = Query(default=12, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MonitorSnapshotResponse:
    """Return the desktop monitor payload in one request.

    This keeps the UI on materialized/read paths and avoids separate polling for
    watchlist signals and the all-strategy priority board.
    """

    return build_monitor_snapshot(
        db,
        current_user=current_user,
        priority_limit=priority_limit,
    )
