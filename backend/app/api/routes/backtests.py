from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.entities import User
from app.models.schema_defs.backtest import (
    BacktestEquityResponse,
    BacktestMutationResponse,
    BacktestRunCreate,
    BacktestRunDetail,
    BacktestRunListResponse,
    BacktestTradesResponse,
)
from app.services.backtest_job_service import BacktestJobService

router = APIRouter(prefix="/backtests", dependencies=[Depends(get_current_user)])


@router.post("", response_model=BacktestRunDetail)
def create_backtest_run(
    payload: BacktestRunCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestRunDetail:
    return BacktestJobService(db).create_run(payload, owner_user_id=current_user.id)


@router.get("", response_model=BacktestRunListResponse)
def list_backtest_runs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None, max_length=24),
    strategy_key: str | None = Query(default=None, max_length=80),
    include_all: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestRunListResponse:
    is_admin = _is_admin(current_user) and include_all
    return BacktestJobService(db).list_runs(
        owner_user_id=current_user.id,
        is_admin=is_admin,
        limit=limit,
        offset=offset,
        status_filter=status,
        strategy_key=strategy_key,
    )


@router.get("/runs")
def list_legacy_backtest_runs(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Compatibility shape for the old research backtest list endpoint."""

    page = BacktestJobService(db).list_runs(
        owner_user_id=current_user.id,
        is_admin=_is_admin(current_user),
        limit=limit,
        offset=0,
    )
    return {
        "runs": [
            {
                "id": item.id,
                "name": item.name,
                "params": {},
                "result": {"status": item.status, "progress_pct": item.progress_pct},
                "created_at": item.created_at,
            }
            for item in page.items
        ]
    }


@router.get("/runs/{run_id}")
def get_legacy_backtest_run(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Compatibility shape for the old research backtest detail endpoint."""

    item = BacktestJobService(db).get_run(
        run_id,
        owner_user_id=current_user.id,
        is_admin=_is_admin(current_user),
    )
    return {
        "id": item.id,
        "name": item.name,
        "params": item.params,
        "result": item.result,
        "created_at": item.created_at,
    }


@router.get("/{run_id}", response_model=BacktestRunDetail)
def get_backtest_run(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestRunDetail:
    return BacktestJobService(db).get_run(
        run_id,
        owner_user_id=current_user.id,
        is_admin=_is_admin(current_user),
    )


@router.get("/{run_id}/equity", response_model=BacktestEquityResponse)
def get_backtest_equity(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestEquityResponse:
    items = BacktestJobService(db).get_equity(
        run_id,
        owner_user_id=current_user.id,
        is_admin=_is_admin(current_user),
    )
    return BacktestEquityResponse(run_id=run_id, items=items)


@router.get("/{run_id}/trades", response_model=BacktestTradesResponse)
def get_backtest_trades(
    run_id: int,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestTradesResponse:
    return BacktestJobService(db).get_trades(
        run_id,
        owner_user_id=current_user.id,
        is_admin=_is_admin(current_user),
        limit=limit,
        offset=offset,
    )


@router.post("/{run_id}/cancel", response_model=BacktestMutationResponse)
def cancel_backtest_run(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestMutationResponse:
    run = BacktestJobService(db).cancel_run(
        run_id,
        owner_user_id=current_user.id,
        is_admin=_is_admin(current_user),
    )
    return BacktestMutationResponse(ok=True, run_id=run.id, status=run.status, message="回测任务已取消")


@router.delete("/{run_id}", response_model=BacktestMutationResponse)
def delete_backtest_run(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestMutationResponse:
    run = BacktestJobService(db).delete_run(
        run_id,
        owner_user_id=current_user.id,
        is_admin=_is_admin(current_user),
    )
    return BacktestMutationResponse(ok=True, run_id=run.id, status=run.status, message="回测任务已删除")


def _is_admin(user: User) -> bool:
    roles = {item.strip().lower() for item in (getattr(user, "roles", "") or "").split(",")}
    return bool(getattr(user, "is_admin", False)) or "admin" in roles or "administrator" in roles
