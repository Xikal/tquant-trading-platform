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
    BacktestVerdictThresholdOut,
    BacktestVerdictThresholdsResponse,
    BacktestValidationCreate,
    BacktestValidationDetail,
    BacktestValidationListResponse,
    EtfT0BacktestRequest,
    EtfT0BacktestResponse,
    EtfT0OosDatasetListResponse,
    EtfT0OosDatasetOut,
    EtfT0OosLatestResponse,
    EtfT0OosPromoteCheckRequest,
    EtfT0OosPromoteCheckResponse,
    EtfT0OosValidationRequest,
    EtfT0OosValidationResponse,
    EtfT0ResearchRequest,
    EtfT0ResearchResponse,
)
from app.api.routes.backtest_route_helpers import (
    is_admin,
    normalized_verdict_thresholds,
    require_optimizer_access,
    require_research_access,
    validate_backtest_strategy_access,
)
from app.services.backtest_job_service import BacktestJobService
from app.services.backtest_optimization_service import BacktestOptimizationService
from app.services.backtest_validation_service import BacktestValidationService
from app.services.backtest.regime_parameter_promotion import promote_regime_parameter_versions
from app.services.position_policy_research import run_position_policy_research
from app.services.portfolio_heuristic_optimizer import optimize_strategy_portfolio
from app.services.live_backtest_monitor import build_live_backtest_comparison
from app.models.schemas import KlineBar
from app.services.etf.oos_dataset import OOSDatasetError, dataset_response, list_oos_datasets, load_oos_dataset
from app.services.etf.oos_validation import latest_oos_validation_summary, promote_check, run_oos_validation
from app.services.etf.t0_backtest import EtfT0MarketRegimeSegment, run_etf_t0_backtest, run_etf_t0_research_report
from app.services.strategy_improvement.report import build_closed_loop_report, default_args_namespace

from pathlib import Path
import json

router = APIRouter(prefix="/backtests", dependencies=[Depends(get_current_user)])

ROOT_DIR = Path(__file__).resolve().parents[4]
DEFAULT_STRATEGY_24M_REPORT = ROOT_DIR / "docs" / "reports" / "strategy-24m-backtest-2026-05-28.json"


@router.get("/verdict-thresholds", response_model=BacktestVerdictThresholdsResponse)
def get_backtest_verdict_thresholds_route() -> BacktestVerdictThresholdsResponse:
    thresholds = normalized_verdict_thresholds()
    return BacktestVerdictThresholdsResponse(
        thresholds={
            key: BacktestVerdictThresholdOut(**values)
            for key, values in thresholds.items()
        }
    )


@router.get("/strategy-improvement-report")
def get_strategy_improvement_report(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_research_access(current_user)
    existing_report = _load_json(DEFAULT_STRATEGY_24M_REPORT)
    return build_closed_loop_report(db, args=default_args_namespace(), existing_report=existing_report)


@router.get("/live-comparison")
def get_live_backtest_comparison(
    account_id: int | None = Query(default=None, ge=1),
    days: int = Query(default=60, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_research_access(current_user)
    return build_live_backtest_comparison(db, user_id=current_user.id, account_id=account_id, days=days)


@router.post("/etf-t0-minute", response_model=EtfT0BacktestResponse)
def run_etf_t0_minute_backtest(
    payload: EtfT0BacktestRequest,
    current_user: User = Depends(get_current_user),
) -> EtfT0BacktestResponse:
    require_research_access(current_user)
    bars = [
        KlineBar(
            timestamp=item.timestamp,
            open=item.open,
            high=item.high,
            low=item.low,
            close=item.close,
            volume=item.volume,
            amount=item.amount,
        )
        for item in payload.bars
    ]
    report = run_etf_t0_backtest(
        symbol=payload.symbol,
        name=payload.name,
        bars=bars,
        quantity=payload.quantity,
        min_signal_bars=payload.min_signal_bars,
        max_trades_per_day=payload.max_trades_per_day,
        params=payload.params,
    )
    return EtfT0BacktestResponse(**report.to_dict())


@router.post("/etf-t0-research", response_model=EtfT0ResearchResponse)
def run_etf_t0_research(
    payload: EtfT0ResearchRequest,
    current_user: User = Depends(get_current_user),
) -> EtfT0ResearchResponse:
    require_research_access(current_user)
    bars = [
        KlineBar(
            timestamp=item.timestamp,
            open=item.open,
            high=item.high,
            low=item.low,
            close=item.close,
            volume=item.volume,
            amount=item.amount,
        )
        for item in payload.bars
    ]
    segments = [
        EtfT0MarketRegimeSegment(
            regime=item.regime,
            start_time=item.start_time,
            end_time=item.end_time,
        )
        for item in payload.market_regime_segments
    ]
    report = run_etf_t0_research_report(
        symbol=payload.symbol,
        name=payload.name,
        bars=bars,
        quantity=payload.quantity,
        min_signal_bars=payload.min_signal_bars,
        max_trades_per_day=payload.max_trades_per_day,
        params=payload.params,
        vwap_deviation_values=payload.vwap_deviation_values,
        oversold_rsi_values=payload.oversold_rsi_values,
        market_regime_segments=segments or None,
    )
    return EtfT0ResearchResponse(**report.to_dict())


def _etf_bars(items) -> list[KlineBar]:
    return [
        KlineBar(
            timestamp=item.timestamp,
            open=item.open,
            high=item.high,
            low=item.low,
            close=item.close,
            volume=item.volume,
            amount=item.amount,
        )
        for item in items
    ]


@router.get("/etf-t0-oos/datasets", response_model=EtfT0OosDatasetListResponse)
def list_etf_t0_oos_datasets(
    current_user: User = Depends(get_current_user),
) -> EtfT0OosDatasetListResponse:
    require_research_access(current_user)
    items = list_oos_datasets()
    return EtfT0OosDatasetListResponse(items=[EtfT0OosDatasetOut(**item) for item in items], total=len(items))


@router.get("/etf-t0-oos/datasets/{dataset_key}", response_model=EtfT0OosDatasetOut)
def get_etf_t0_oos_dataset(
    dataset_key: str,
    current_user: User = Depends(get_current_user),
) -> EtfT0OosDatasetOut:
    require_research_access(current_user)
    try:
        return EtfT0OosDatasetOut(**dataset_response(load_oos_dataset(dataset_key)))
    except OOSDatasetError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/etf-t0-oos/validate", response_model=EtfT0OosValidationResponse)
def validate_etf_t0_oos(
    payload: EtfT0OosValidationRequest,
    current_user: User = Depends(get_current_user),
) -> EtfT0OosValidationResponse:
    require_research_access(current_user)
    try:
        result = run_oos_validation(
            dataset_key=payload.dataset_key,
            symbol=payload.symbol,
            name=payload.name,
            bars=_etf_bars(payload.bars),
            quantity=payload.quantity,
            min_signal_bars=payload.min_signal_bars,
            max_trades_per_day=payload.max_trades_per_day,
            params=payload.params,
            vwap_deviation_values=payload.vwap_deviation_values,
            oversold_rsi_values=payload.oversold_rsi_values,
        )
    except OOSDatasetError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return EtfT0OosValidationResponse(**result)


@router.post("/etf-t0-oos/promote-check", response_model=EtfT0OosPromoteCheckResponse)
def etf_t0_oos_promote_check(
    payload: EtfT0OosPromoteCheckRequest,
    current_user: User = Depends(get_current_user),
) -> EtfT0OosPromoteCheckResponse:
    require_research_access(current_user)
    try:
        result = promote_check(
            dataset_key=payload.dataset_key,
            symbol=payload.symbol,
            name=payload.name,
            bars=_etf_bars(payload.bars),
            quantity=payload.quantity,
            min_signal_bars=payload.min_signal_bars,
            max_trades_per_day=payload.max_trades_per_day,
            params=payload.params,
            vwap_deviation_values=payload.vwap_deviation_values,
            oversold_rsi_values=payload.oversold_rsi_values,
        )
    except OOSDatasetError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return EtfT0OosPromoteCheckResponse(**result)


@router.get("/etf-t0-oos/latest", response_model=EtfT0OosLatestResponse)
def latest_etf_t0_oos_validation(
    current_user: User = Depends(get_current_user),
) -> EtfT0OosLatestResponse:
    require_research_access(current_user)
    return EtfT0OosLatestResponse(**latest_oos_validation_summary())


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@router.post("", response_model=BacktestRunDetail)
def create_backtest_run(
    payload: BacktestRunCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestRunDetail:
    validate_backtest_strategy_access(db, payload.strategy_keys, current_user)
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
    include_admin_runs = is_admin(current_user) and include_all
    return BacktestJobService(db).list_runs(
        owner_user_id=current_user.id,
        is_admin=include_admin_runs,
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
        is_admin=is_admin(current_user),
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
        is_admin=is_admin(current_user),
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
    require_optimizer_access(current_user)
    validate_backtest_strategy_access(db, [payload.strategy], current_user)
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
    require_optimizer_access(current_user)
    return BacktestOptimizationService(db).list_tasks(
        owner_user_id=current_user.id,
        is_admin=is_admin(current_user) and include_all,
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
    require_optimizer_access(current_user)
    return BacktestOptimizationService(db).get_task(
        task_id,
        owner_user_id=current_user.id,
        is_admin=is_admin(current_user),
    )


@router.post("/optimize/{task_id}/cancel", response_model=BacktestResearchMutationResponse)
def cancel_backtest_optimization(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestResearchMutationResponse:
    require_optimizer_access(current_user)
    task = BacktestOptimizationService(db).cancel_task(
        task_id,
        owner_user_id=current_user.id,
        is_admin=is_admin(current_user),
    )
    return BacktestResearchMutationResponse(ok=True, task_id=task.id, status=task.status, message="优化任务已取消")


@router.delete("/optimize/{task_id}", response_model=BacktestResearchMutationResponse)
def delete_backtest_optimization(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestResearchMutationResponse:
    require_optimizer_access(current_user)
    task = BacktestOptimizationService(db).delete_task(
        task_id,
        owner_user_id=current_user.id,
        is_admin=is_admin(current_user),
    )
    return BacktestResearchMutationResponse(ok=True, task_id=task.id, status=task.status, message="优化任务已删除")


@router.post("/validate", response_model=BacktestValidationDetail)
def create_backtest_validation(
    payload: BacktestValidationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestValidationDetail:
    require_research_access(current_user)
    if payload.auto_promote_state_params:
        require_optimizer_access(current_user)
    validate_backtest_strategy_access(db, [payload.strategy], current_user)
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
    require_research_access(current_user)
    return BacktestValidationService(db).list_tasks(
        owner_user_id=current_user.id,
        is_admin=is_admin(current_user) and include_all,
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
    require_research_access(current_user)
    return BacktestValidationService(db).get_task(
        task_id,
        owner_user_id=current_user.id,
        is_admin=is_admin(current_user),
    )


@router.post("/validate/{task_id}/cancel", response_model=BacktestResearchMutationResponse)
def cancel_backtest_validation(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestResearchMutationResponse:
    require_research_access(current_user)
    task = BacktestValidationService(db).cancel_task(
        task_id,
        owner_user_id=current_user.id,
        is_admin=is_admin(current_user),
    )
    return BacktestResearchMutationResponse(ok=True, task_id=task.id, status=task.status, message="验证任务已取消")


@router.delete("/validate/{task_id}", response_model=BacktestResearchMutationResponse)
def delete_backtest_validation(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestResearchMutationResponse:
    require_research_access(current_user)
    task = BacktestValidationService(db).delete_task(
        task_id,
        owner_user_id=current_user.id,
        is_admin=is_admin(current_user),
    )
    return BacktestResearchMutationResponse(ok=True, task_id=task.id, status=task.status, message="验证任务已删除")


@router.post("/validate/{task_id}/promote-state-params")
def promote_validation_state_params(
    task_id: int,
    activate: bool = Query(default=True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_optimizer_access(current_user)
    detail = BacktestValidationService(db).get_task(
        task_id,
        owner_user_id=current_user.id,
        is_admin=is_admin(current_user),
    )
    if detail.status != "succeeded":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="验证任务未成功，不能晋级参数")
    return promote_regime_parameter_versions(
        db,
        validation_result=detail.result,
        strategy_key=detail.strategy_key,
        operator=current_user.username or str(current_user.id),
        activate=activate,
    )


@router.post("/compare", response_model=BacktestCompareResponse)
def compare_backtest_runs(
    payload: BacktestCompareRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestCompareResponse:
    return BacktestJobService(db).compare_runs(
        payload,
        owner_user_id=current_user.id,
        is_admin=is_admin(current_user),
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
        is_admin=is_admin(current_user),
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
        is_admin=is_admin(current_user),
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
        is_admin=is_admin(current_user),
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
        is_admin=is_admin(current_user),
    )


@router.get("/{run_id}/portfolio-optimization")
def get_backtest_portfolio_optimization(
    run_id: int,
    method: str = Query(default="hrp", pattern="^(hrp|risk_adjusted|markowitz|black_litterman|bl)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_research_access(current_user)
    BacktestJobService(db).get_run(run_id, owner_user_id=current_user.id, is_admin=is_admin(current_user))
    return optimize_strategy_portfolio(db, run_id=run_id, method=method)


@router.get("/{run_id}/position-policy-research")
def get_backtest_position_policy_research(
    run_id: int,
    train_shadow: bool = Query(default=False, description="仅后台/管理员研究使用；默认不在请求线程训练 RL shadow"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_research_access(current_user)
    if train_shadow:
        require_optimizer_access(current_user)
    BacktestJobService(db).get_run(run_id, owner_user_id=current_user.id, is_admin=is_admin(current_user))
    return run_position_policy_research(db, run_id=run_id, train_shadow=train_shadow)


@router.get("/{run_id}/equity", response_model=BacktestEquityResponse)
def get_backtest_equity(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestEquityResponse:
    items = BacktestJobService(db).get_equity(
        run_id,
        owner_user_id=current_user.id,
        is_admin=is_admin(current_user),
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
        is_admin=is_admin(current_user),
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
        is_admin=is_admin(current_user),
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
        is_admin=is_admin(current_user),
    )
    return BacktestMutationResponse(ok=True, run_id=run.id, status=run.status, message="回测任务已删除")
