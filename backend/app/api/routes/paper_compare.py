from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.paper_auth import require_paper_trading
from app.models.entities import User
from app.models.schema_defs.phase4 import PaperBacktestComparisonRequest, RuntimeTaskOut
from app.api.routes.heavy_task_helpers import enqueue_runtime_task
from app.services.paper import PaperAccountService

router = APIRouter(prefix="/paper")


@router.post("/backtest-comparison", response_model=RuntimeTaskOut, status_code=status.HTTP_202_ACCEPTED)
def compare_paper_with_backtest(
    payload: PaperBacktestComparisonRequest,
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> RuntimeTaskOut:
    account_id = payload.account_id
    if account_id is None:
        account_id = PaperAccountService(db).get_or_create_default(current_user.id).id
    try:
        return enqueue_runtime_task(
            db,
            task_type="paper_backtest_comparison",
            payload={
                "account_id": account_id,
                "backtest_run_id": payload.backtest_run_id,
                "deviation_threshold_pct": payload.deviation_threshold_pct,
                "owner_user_id": current_user.id,
            },
            priority=210,
            idempotency_key=f"paper_backtest_comparison:{current_user.id}:{account_id}:{payload.backtest_run_id}",
            max_attempts=2,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
