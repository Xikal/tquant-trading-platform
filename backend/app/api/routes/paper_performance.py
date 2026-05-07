from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_auth
from app.core.database import get_db
from app.core.paper_auth import require_paper_trading
from app.models.entities import User
from app.models.schemas import (
    PaperGroupedPerformanceOut,
    PaperPerformanceOut,
    PaperStrategyCorrelationResponse,
    PaperStrategyMarketPerformanceOut,
    PaperTagPerformanceOut,
)
from app.services.paper import PaperAccountService, PaperArchiveService, PaperPerformanceService
from app.services.paper.dashboard import PaperPerformanceDashboardService

router = APIRouter()


@router.get("/performance", response_model=PaperPerformanceOut)
def paper_performance(
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperPerformanceOut:
    account_service = PaperAccountService(db)
    account = account_service.get_or_create_default(current_user.id)
    account_service.update_market_value(account.id)
    return PaperPerformanceOut(**PaperPerformanceService(db).compute_overall(account.id))


@router.get("/performance/by-strategy", response_model=list[PaperGroupedPerformanceOut])
def paper_performance_by_strategy(
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> list[PaperGroupedPerformanceOut]:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    return [PaperGroupedPerformanceOut(**item) for item in PaperPerformanceService(db).compute_by_strategy(account.id)]


@router.get("/performance/by-market-state", response_model=list[PaperGroupedPerformanceOut])
def paper_performance_by_market_state(
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> list[PaperGroupedPerformanceOut]:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    return [PaperGroupedPerformanceOut(**item) for item in PaperPerformanceService(db).compute_by_market_state(account.id)]


@router.get("/performance/by-strategy-market-state", response_model=list[PaperStrategyMarketPerformanceOut])
def paper_performance_by_strategy_market_state(
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> list[PaperStrategyMarketPerformanceOut]:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    return [
        PaperStrategyMarketPerformanceOut(**item)
        for item in PaperPerformanceService(db).compute_by_strategy_market_state(account.id)
    ]


@router.get("/performance/by-tag", response_model=list[PaperTagPerformanceOut])
def paper_performance_by_tag(
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> list[PaperTagPerformanceOut]:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    return [PaperTagPerformanceOut(**item) for item in PaperPerformanceService(db).compute_by_tag(account.id)]


@router.get("/performance/strategy-correlation", response_model=PaperStrategyCorrelationResponse)
def paper_performance_strategy_correlation(
    days: int = Query(default=90, ge=7, le=730),
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperStrategyCorrelationResponse:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    start_date = None
    if days > 0:
        start_date = date.today() - timedelta(days=days)
    payload = PaperPerformanceService(db).compute_strategy_correlation(account.id, start_date=start_date)
    return PaperStrategyCorrelationResponse(**payload)


@router.get("/performance/dashboard")
def paper_performance_dashboard(
    days: int = Query(default=30, ge=7, le=365),
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> dict:
    account_service = PaperAccountService(db)
    account = account_service.get_or_create_default(current_user.id)
    account_service.update_market_value(account.id)
    return PaperPerformanceDashboardService(db).build(account, days)


@router.post("/performance/archive")
def archive_paper_performance(
    current_user: User = Depends(require_paper_trading),
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> dict:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    return PaperArchiveService(db).archive_all(account.id)
