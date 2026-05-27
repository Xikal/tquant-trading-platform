from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.config import get_settings
from app.core.database import get_db
from app.services.low_buy_materialization import enqueue_low_buy_materialization_run
from sqlalchemy.orm import Session


def _require_internal_token(request: Request) -> None:
    expected = get_settings().tquant_internal_service_token.strip()
    provided = request.headers.get("x-internal-service-token", "").strip()
    if not expected or provided != expected:
        raise HTTPException(status_code=403, detail="internal service auth failed")


router = APIRouter(prefix="/internal/scan-worker/v1", dependencies=[Depends(_require_internal_token)])


@router.get("/run", status_code=status.HTTP_202_ACCEPTED)
def run_scan_worker_reference(
    strategies: str = Query(default=""),
    scan_limit: int = Query(default=480, ge=1, le=10000),
    limit: int = Query(default=40, ge=1, le=500),
    reason: str = Query(default="go_scan_worker"),
    db: Session = Depends(get_db),
) -> dict:
    strategy_list = [item.strip() for item in strategies.split(",") if item.strip()]
    result = enqueue_low_buy_materialization_run(
        db,
        strategies=strategy_list,
        limit=limit,
        scan_limit=scan_limit,
        reason=reason,
    )
    return {
        **result,
        "reason": reason,
        "production_scan_enabled": True,
        "production_write_enabled": True,
        "scan_worker_role": "go_orchestrated_reference",
        "strategy_engine": "python_reference",
        "ranking_consistency": {
            "checked": True,
            "status": "python_reference_order",
            "detail": "Go scan-worker enqueued the Python strategy reference and latest is published only after the reference write succeeds.",
        },
    }
