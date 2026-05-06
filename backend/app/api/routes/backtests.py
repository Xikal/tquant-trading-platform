from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.entities import User
from app.models.schema_defs.backtest import (
    BacktestAttributionResponse,
    BacktestCompareRequest,
    BacktestCompareResponse,
    BacktestEquityResponse,
    BacktestMutationResponse,
    BacktestOptimizationCreate,
    BacktestOptimizationDetail,
    BacktestOptimizationListResponse,
    BacktestResearchMutationResponse,
    BacktestMonthlyReturnsResponse,
    BacktestRunCreate,
    BacktestRunDetail,
    BacktestRunListResponse,
    BacktestStrategyCorrelationResponse,
    BacktestTradesResponse,
    BacktestValidationCreate,
    BacktestValidationDetail,
    BacktestValidationListResponse,
)
from app.services.backtest_job_service import BacktestJobService
from app.services.backtest_optimization_service import BacktestOptimizationService
from app.services.backtest_validation_service import BacktestValidationService
from app.services.strategy_metadata_service import StrategyMetadataService

router = APIRouter(prefix="/backtests", dependencies=[Depends(get_current_user)])


@router.post("", response_model=BacktestRunDetail)
def create_backtest_run(
    payload: BacktestRunCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestRunDetail:
    _validate_backtest_strategy_access(db, payload.strategy_keys, current_user)
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


@router.post("/optimize", response_model=BacktestOptimizationDetail)
def create_backtest_optimization(
    payload: BacktestOptimizationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestOptimizationDetail:
    _require_optimizer_access(current_user)
    _validate_backtest_strategy_access(db, [payload.strategy], current_user)
    return BacktestOptimizationService(db).create_task(payload, owner_user_id=current_user.id)


@router.get("/optimize", response_model=BacktestOptimizationListResponse)
def list_backtest_optimizations(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status", max_length=24),
    include_all: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestOptimizationListResponse:
    _require_optimizer_access(current_user)
    return BacktestOptimizationService(db).list_tasks(
        owner_user_id=current_user.id,
        is_admin=_is_admin(current_user) and include_all,
        limit=limit,
        offset=offset,
        status_filter=status_filter,
    )


@router.get("/optimize/{task_id}", response_model=BacktestOptimizationDetail)
def get_backtest_optimization(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestOptimizationDetail:
    _require_optimizer_access(current_user)
    return BacktestOptimizationService(db).get_task(
        task_id,
        owner_user_id=current_user.id,
        is_admin=_is_admin(current_user),
    )


@router.post("/optimize/{task_id}/cancel", response_model=BacktestResearchMutationResponse)
def cancel_backtest_optimization(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestResearchMutationResponse:
    _require_optimizer_access(current_user)
    task = BacktestOptimizationService(db).cancel_task(
        task_id,
        owner_user_id=current_user.id,
        is_admin=_is_admin(current_user),
    )
    return BacktestResearchMutationResponse(ok=True, task_id=task.id, status=task.status, message="优化任务已取消")


@router.delete("/optimize/{task_id}", response_model=BacktestResearchMutationResponse)
def delete_backtest_optimization(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestResearchMutationResponse:
    _require_optimizer_access(current_user)
    task = BacktestOptimizationService(db).delete_task(
        task_id,
        owner_user_id=current_user.id,
        is_admin=_is_admin(current_user),
    )
    return BacktestResearchMutationResponse(ok=True, task_id=task.id, status=task.status, message="优化任务已删除")


@router.post("/validate", response_model=BacktestValidationDetail)
def create_backtest_validation(
    payload: BacktestValidationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestValidationDetail:
    _require_research_access(current_user)
    _validate_backtest_strategy_access(db, [payload.strategy], current_user)
    return BacktestValidationService(db).create_task(payload, owner_user_id=current_user.id)


@router.get("/validate", response_model=BacktestValidationListResponse)
def list_backtest_validations(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status", max_length=24),
    include_all: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestValidationListResponse:
    _require_research_access(current_user)
    return BacktestValidationService(db).list_tasks(
        owner_user_id=current_user.id,
        is_admin=_is_admin(current_user) and include_all,
        limit=limit,
        offset=offset,
        status_filter=status_filter,
    )


@router.get("/validate/{task_id}", response_model=BacktestValidationDetail)
def get_backtest_validation(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestValidationDetail:
    _require_research_access(current_user)
    return BacktestValidationService(db).get_task(
        task_id,
        owner_user_id=current_user.id,
        is_admin=_is_admin(current_user),
    )


@router.post("/validate/{task_id}/cancel", response_model=BacktestResearchMutationResponse)
def cancel_backtest_validation(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestResearchMutationResponse:
    _require_research_access(current_user)
    task = BacktestValidationService(db).cancel_task(
        task_id,
        owner_user_id=current_user.id,
        is_admin=_is_admin(current_user),
    )
    return BacktestResearchMutationResponse(ok=True, task_id=task.id, status=task.status, message="验证任务已取消")


@router.delete("/validate/{task_id}", response_model=BacktestResearchMutationResponse)
def delete_backtest_validation(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestResearchMutationResponse:
    _require_research_access(current_user)
    task = BacktestValidationService(db).delete_task(
        task_id,
        owner_user_id=current_user.id,
        is_admin=_is_admin(current_user),
    )
    return BacktestResearchMutationResponse(ok=True, task_id=task.id, status=task.status, message="验证任务已删除")


@router.post("/compare", response_model=BacktestCompareResponse)
def compare_backtest_runs(
    payload: BacktestCompareRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestCompareResponse:
    return BacktestJobService(db).compare_runs(
        payload,
        owner_user_id=current_user.id,
        is_admin=_is_admin(current_user),
    )


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


@router.get("/{run_id}/monthly-returns", response_model=BacktestMonthlyReturnsResponse)
def get_backtest_monthly_returns(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestMonthlyReturnsResponse:
    return BacktestJobService(db).get_monthly_returns(
        run_id,
        owner_user_id=current_user.id,
        is_admin=_is_admin(current_user),
    )


@router.get("/{run_id}/attribution", response_model=BacktestAttributionResponse)
def get_backtest_attribution(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestAttributionResponse:
    return BacktestJobService(db).get_attribution(
        run_id,
        owner_user_id=current_user.id,
        is_admin=_is_admin(current_user),
    )


@router.get("/{run_id}/strategy-correlation", response_model=BacktestStrategyCorrelationResponse)
def get_backtest_strategy_correlation(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestStrategyCorrelationResponse:
    return BacktestJobService(db).get_strategy_correlation(
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


def _require_optimizer_access(user: User) -> None:
    roles = {item.strip().lower() for item in (getattr(user, "roles", "") or "").split(",")}
    if _is_admin(user) or "backtest_optimizer" in roles:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号未开通参数优化权限")


def _require_research_access(user: User) -> None:
    roles = {item.strip().lower() for item in (getattr(user, "roles", "") or "").split(",")}
    if _is_admin(user) or {"backtest_optimizer", "backtest_research"} & roles:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号未开通样本外验证权限")


def _validate_backtest_strategy_access(db: Session, strategy_keys: list[str], user: User) -> None:
    try:
        StrategyMetadataService(db).validate_backtest_strategy_access(strategy_keys, current_user=user)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
