from __future__ import annotations

from datetime import date, timedelta
from typing import Union

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_auth
from app.core.database import get_db
from app.core.paper_auth import require_paper_trading
from app.models.entities import User
from app.models.schemas import (
    PaperGroupedPerformanceOut,
    PaperPerformanceOut,
    PaperSectorEtfT0PerformanceOut,
    PaperSmartTBacktestResponse,
    PaperStockPnlResponse,
    PaperStrategyCorrelationResponse,
    PaperStrategyMarketPerformanceOut,
    PaperTagPerformanceOut,
)
from app.models.schema_defs.phase4 import RuntimeTaskOut
from app.models.schema_defs.market import MarketReviewReportOut, MarketReviewStatusOut
from app.api.routes.heavy_task_helpers import enqueue_runtime_task, queued_task_response
from app.services.paper import PaperAccountService, PaperArchiveService, PaperPerformanceService
from app.services.paper.dashboard import PaperPerformanceDashboardService
from app.services.paper.smart_t_backtest import SmartTBacktestService
from app.services.paper.stock_pnl import PaperStockPnlService
from app.services.market_model_observation_service import MarketModelObservationService
from app.services.monitor_review import build_monitor_review_summary, list_monitor_review_history

router = APIRouter()


@router.get("/performance", response_model=PaperPerformanceOut)
def paper_performance(
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperPerformanceOut:
    account_service = PaperAccountService(db)
    account = account_service.get_or_create_default(current_user.id)
    account_service.update_market_value(account.id)
    service = PaperPerformanceService(db)
    payload = service.compute_overall(account.id)
    payload["portfolio_execution_preview"] = service.compute_portfolio_execution_preview(account.id)
    return PaperPerformanceOut(**payload)


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


@router.get("/performance/sector-etf-t0", response_model=PaperSectorEtfT0PerformanceOut)
def paper_performance_sector_etf_t0(
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperSectorEtfT0PerformanceOut:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    simulated = PaperPerformanceService(db).compute_sector_etf_t0(account.id)
    shadow = MarketModelObservationService().summarize(db, model_key="sector_etf_t0", lookback_days=60)
    return PaperSectorEtfT0PerformanceOut(
        **simulated,
        shadow_sample_count=int(shadow["sample_count"]),
        shadow_settled_count=int(shadow["settled_count"]),
        shadow_pending_count=int(shadow["pending_count"]),
        shadow_success_rate_pct=round(float(shadow["success_rate_pct"] or 0.0), 2),
        shadow_avg_return_1d_pct=round(float(shadow["avg_return_1d_pct"] or 0.0), 2),
        shadow_avg_return_3d_pct=round(float(shadow["avg_return_3d_pct"] or 0.0), 2),
    )


@router.get("/performance/stock-pnl", response_model=PaperStockPnlResponse)
def paper_performance_stock_pnl(
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperStockPnlResponse:
    account_service = PaperAccountService(db)
    account = account_service.get_or_create_default(current_user.id)
    account_service.update_market_value(account.id)
    return PaperStockPnlResponse(**PaperStockPnlService(db).summary(account.id))


@router.get("/performance/smart-t-backtest", response_model=Union[PaperSmartTBacktestResponse, RuntimeTaskOut])
def paper_performance_smart_t_backtest(
    start_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    strategies: list[str] | None = Query(default=None),
    max_signals_per_day: int = Query(default=20, ge=1, le=100),
    forward_days: int = Query(default=3, ge=1, le=10),
    sample_limit: int = Query(default=50, ge=0, le=200),
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperSmartTBacktestResponse:
    if _smart_t_backtest_requires_queue(start_date=start_date, end_date=end_date, sample_limit=sample_limit):
        return queued_task_response(
            enqueue_runtime_task(
                db,
                task_type="paper_smart_t_backtest",
                payload={
                    "start_date": start_date,
                    "end_date": end_date,
                    "strategies": strategies or [],
                    "max_signals_per_day": max_signals_per_day,
                    "forward_days": forward_days,
                    "sample_limit": sample_limit,
                    "owner_user_id": current_user.id,
                },
                priority=210,
                idempotency_key=f"paper_smart_t_backtest:{current_user.id}:{start_date or ''}:{end_date or ''}:{sample_limit}",
                max_attempts=2,
            )
        )
    report = SmartTBacktestService(db).run(
        start_date=start_date,
        end_date=end_date,
        strategies=strategies,
        max_signals_per_day=max_signals_per_day,
        forward_days=forward_days,
        sample_limit=sample_limit,
    )
    return PaperSmartTBacktestResponse(**_report_dict(report))


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


@router.get("/performance/review-summary")
def paper_performance_review_summary(
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> dict[str, MarketReviewStatusOut | list[MarketReviewReportOut]]:
    status, reports = build_monitor_review_summary(db, user_id=current_user.id)
    return {"review_status": status, "review_reports": [_review_entry_metadata(report) for report in reports]}


@router.get("/performance/review-history")
def paper_performance_review_history(
    limit: int = Query(default=20, ge=1, le=200),
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> dict[str, list[MarketReviewReportOut] | int]:
    reports = list_monitor_review_history(db, user_id=current_user.id, limit=limit)
    return {"items": [_review_entry_metadata(report) for report in reports], "total": len(reports)}


@router.post("/performance/archive")
def archive_paper_performance(
    current_user: User = Depends(require_paper_trading),
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> dict:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    return PaperArchiveService(db).archive_all(account.id)


def _review_entry_metadata(report: MarketReviewReportOut) -> MarketReviewReportOut:
    """Paper routes expose navigation metadata; realtime monitor owns review content."""

    return report.model_copy(
        update={
            "overall_summary": "",
            "strategy_highlights": [],
            "risk_alerts": [],
            "suggestion": "",
            "missing_data": [],
            "autofill_details": [],
            "llm_model": "",
        }
    )


def _report_dict(report) -> dict:
    return {
        **report.__dict__,
        "threshold_stats": [item.__dict__ for item in report.threshold_stats],
        "samples": [item.__dict__ for item in report.samples],
    }


def _smart_t_backtest_requires_queue(*, start_date: str | None, end_date: str | None, sample_limit: int) -> bool:
    if sample_limit > 120:
        return True
    return bool(start_date and end_date)
