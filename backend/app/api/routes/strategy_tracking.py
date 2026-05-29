from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_auth
from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.timing import log_slow_call, monotonic_start
from app.models.schema_defs.strategy_tracking import (
    StrategyTrackingDetailResponse,
    StrategyTrackingListResponse,
    StrategyTrackingPerformanceOut,
    StrategyTrackingRefreshResponse,
    StrategyTrackingSummaryOut,
)
from app.services.strategy_tracking import DEFAULT_LIMIT, DEFAULT_RANGE_DAYS, StrategyTrackingService

router = APIRouter(prefix="/strategy-tracking", dependencies=[Depends(get_current_user)])
logger = logging.getLogger(__name__)


@router.get("/summary", response_model=StrategyTrackingSummaryOut)
def strategy_tracking_summary_view(
    range_days: int = Query(DEFAULT_RANGE_DAYS, ge=1, le=260, alias="range"),
    strategy_key: str | None = Query(None),
    strategy_family: str | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
):
    started_at = monotonic_start()
    try:
        return StrategyTrackingService(db).summary(
            range_days=range_days,
            strategy_key=strategy_key,
            strategy_family=strategy_family,
            lifecycle_status=status,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"策略跟踪总览加载失败: {exc}") from exc
    finally:
        log_slow_call(logger, "strategy_tracking.summary", started_at, range_days=range_days, strategy_key=strategy_key)


@router.get("/items", response_model=StrategyTrackingListResponse)
def strategy_tracking_items_view(
    range_days: int = Query(DEFAULT_RANGE_DAYS, ge=1, le=260, alias="range"),
    status: str | None = Query(None),
    signal_state: str | None = Query(None),
    strategy_key: str | None = Query(None),
    strategy_family: str | None = Query(None),
    data_quality: str | None = Query(None),
    hit_entry: bool | None = Query(None),
    stopped: bool | None = Query(None),
    sort: str = Query("max_gain_desc"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    started_at = monotonic_start()
    try:
        return StrategyTrackingService(db).list_items(
            range_days=range_days,
            strategy_key=strategy_key,
            strategy_family=strategy_family,
            lifecycle_status=status,
            signal_state=signal_state,
            data_quality=data_quality,
            hit_entry=hit_entry,
            stopped=stopped,
            sort=sort,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"策略跟踪列表加载失败: {exc}") from exc
    finally:
        log_slow_call(
            logger,
            "strategy_tracking.items",
            started_at,
            range_days=range_days,
            strategy_key=strategy_key,
            limit=limit,
            offset=offset,
        )


@router.get("/performance", response_model=list[StrategyTrackingPerformanceOut])
def strategy_tracking_performance_view(
    range_days: int = Query(DEFAULT_RANGE_DAYS, ge=1, le=260, alias="range"),
    strategy_family: str | None = Query(None),
    db: Session = Depends(get_db),
):
    started_at = monotonic_start()
    try:
        return StrategyTrackingService(db).performance(range_days=range_days, strategy_family=strategy_family)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"策略跟踪表现加载失败: {exc}") from exc
    finally:
        log_slow_call(logger, "strategy_tracking.performance", started_at, range_days=range_days)


@router.get("/items/{item_id}", response_model=StrategyTrackingDetailResponse)
def strategy_tracking_detail_view(item_id: str, db: Session = Depends(get_db)):
    started_at = monotonic_start()
    try:
        return StrategyTrackingService(db).detail(item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"策略跟踪详情加载失败: {exc}") from exc
    finally:
        log_slow_call(logger, "strategy_tracking.detail", started_at, item_id=item_id)


@router.post("/refresh", response_model=StrategyTrackingRefreshResponse)
def strategy_tracking_refresh_view(
    range_days: int = Query(DEFAULT_RANGE_DAYS, ge=1, le=260, alias="range"),
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
):
    started_at = monotonic_start()
    try:
        return StrategyTrackingService(db).refresh(range_days=range_days)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"策略跟踪刷新失败: {exc}") from exc
    finally:
        log_slow_call(logger, "strategy_tracking.refresh", started_at, range_days=range_days)
