import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.role_permissions import is_admin_user
from app.models.entities import BacktestRun, User
from app.models.schemas import (
    LegacyResearchBacktestRequest,
    BacktestRunListResponse,
    BacktestRunOut,
    StrategyComparisonRequest,
    StrategyValidationReport,
    StrategyValidationRequest,
)
from app.services.analysis_service import AnalysisService
from app.services.market_data import MarketDataService
from app.services.paper.validation import StrategyValidationPipeline

router = APIRouter(dependencies=[Depends(get_current_user)])
analysis_service = AnalysisService()
market_data = MarketDataService()


@router.get("/replays")
def get_replays(db: Session = Depends(get_db), limit: int = 100):
    items = analysis_service.research_service.list_replays(db, limit=limit)
    return [item.model_dump() for item in items]


@router.post("/backtests", include_in_schema=False)
def run_backtest(
    payload: LegacyResearchBacktestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    instrument = market_data.get_instrument(db, payload.symbol)
    result = analysis_service.run_backtest(db, payload, instrument, owner_user_id=current_user.id)
    return result.model_dump()


@router.get("/backtests/runs", response_model=BacktestRunListResponse)
def list_backtest_runs(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestRunListResponse:
    statement = select(BacktestRun).order_by(BacktestRun.id.desc()).limit(limit)
    if not is_admin_user(current_user):
        statement = statement.where(BacktestRun.owner_user_id == current_user.id)
    rows = db.execute(statement).scalars().all()
    return BacktestRunListResponse(runs=[_backtest_run_out(row) for row in rows])


@router.get("/backtests/runs/{run_id}", response_model=BacktestRunOut)
def get_backtest_run(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestRunOut:
    row = db.get(BacktestRun, run_id)
    if row is None or (not is_admin_user(current_user) and row.owner_user_id != current_user.id):
        raise HTTPException(status_code=404, detail="回测报告不存在")
    return _backtest_run_out(row)


@router.post(
    "/strategy-validation",
    response_model=StrategyValidationReport,
    summary="策略快速验证",
    description="交互式快速回放接口，不替代正式 Walk-forward 回测验证。",
)
def run_strategy_validation(payload: StrategyValidationRequest, db: Session = Depends(get_db)):
    return StrategyValidationPipeline(db).validate(payload)


@router.post(
    "/strategy-validation/compare",
    response_model=StrategyValidationReport,
    summary="策略快速对比",
    description="基于快速验证结果排序，用于筛查候选策略；正式结论以回测系统为准。",
)
def compare_strategy_validation(payload: StrategyComparisonRequest, db: Session = Depends(get_db)):
    return StrategyValidationPipeline(db).compare_strategies(payload)


def _backtest_run_out(row: BacktestRun) -> BacktestRunOut:
    return BacktestRunOut(
        id=row.id,
        name=row.name or "",
        params=_json_dict(row.params_json),
        result=_json_dict(row.result_json),
        created_at=row.created_at,
    )


def _json_dict(raw_value: str) -> dict:
    try:
        value = json.loads(raw_value or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}
