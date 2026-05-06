from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.paper_auth import require_paper_trading
from app.models.entities import User
from app.models.schema_defs.phase4 import PaperBacktestComparisonRequest, PaperBacktestComparisonResponse
from app.services.paper import PaperAccountService
from app.services.paper.backtest_compare import PaperBacktestComparisonService

router = APIRouter(prefix="/paper")


@router.post("/backtest-comparison", response_model=PaperBacktestComparisonResponse)
def compare_paper_with_backtest(
    payload: PaperBacktestComparisonRequest,
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperBacktestComparisonResponse:
    account_id = payload.account_id
    if account_id is None:
        account_id = PaperAccountService(db).get_or_create_default(current_user.id).id
    try:
        return PaperBacktestComparisonService(db).compare(
            account_id=account_id,
            backtest_run_id=payload.backtest_run_id,
            deviation_threshold_pct=payload.deviation_threshold_pct,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
