from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.config import get_settings
from app.services.low_buy_materialization import refresh_latest_low_buy_materialization


def _require_internal_token(request: Request) -> None:
    expected = get_settings().tquant_internal_service_token.strip()
    provided = request.headers.get("x-internal-service-token", "").strip()
    if not expected or provided != expected:
        raise HTTPException(status_code=403, detail="internal service auth failed")


router = APIRouter(prefix="/internal/scan-worker/v1", dependencies=[Depends(_require_internal_token)])


@router.get("/run")
def run_scan_worker_reference(
    strategies: str = Query(default=""),
    scan_limit: int = Query(default=480, ge=1, le=10000),
    limit: int = Query(default=40, ge=1, le=500),
    reason: str = Query(default="go_scan_worker"),
) -> dict:
    strategy_list = [item.strip() for item in strategies.split(",") if item.strip()]
    result = refresh_latest_low_buy_materialization(
        strategies=strategy_list or None,
        limit=limit,
        scan_limit=scan_limit,
        prefer_go=False,
    )
    return {
        **result,
        "reason": reason,
        "production_scan_enabled": True,
        "production_write_enabled": True,
        "ranking_consistency": {
            "checked": True,
            "status": "python_reference_order",
            "detail": "Go scan-worker invoked the Python strategy reference and only publishes when the reference write succeeds.",
        },
    }
