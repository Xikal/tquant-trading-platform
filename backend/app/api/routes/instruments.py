from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_auth
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.instrument_sync_status import InstrumentSyncStatusService
from app.services.market_data import DataSourceError, MarketDataService
from app.services.market_rules import MarketRuleService
from app.services.tasks import RuntimeTaskQueue

router = APIRouter(dependencies=[Depends(get_current_user)])
logger = logging.getLogger(__name__)
market_data = MarketDataService()
rule_service = MarketRuleService()
sync_status = InstrumentSyncStatusService()


@router.get("/instruments")
def list_instruments(
    keyword: str = "",
    kind: str = Query("all", pattern="^(all|stock|etf)$"),
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
):
    if market_data.get_total_instruments(db, kind="all") == 0:
        try:
            market_data.sync_instruments(db, "all")
        except Exception:
            logger.warning("instrument bootstrap sync failed", exc_info=True)
    items = market_data.search_instruments(db, keyword=keyword, kind=kind, page=page, page_size=page_size)
    total = market_data.get_total_instruments(db, kind=kind)
    return {"items": [item.model_dump() for item in items], "page": page, "page_size": page_size, "total": total}


@router.post("/instruments/sync")
def sync_instruments(
    kind: str = Query("all", pattern="^(all|stock|etf)$"),
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
):
    run_id = sync_status.start(kind=kind)
    try:
        task = RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
                task_type="instrument_sync",
                payload={"kind": kind, "run_id": run_id},
                priority=20,
                max_attempts=1,
            )
        )
        sync_status.update(
            run_id=run_id,
            kind=kind,
            status="queued",
            progress_pct=3.0,
            message="股票库更新任务已入队",
            task_id=int(task.id),
        )
    except Exception as exc:
        sync_status.fail(run_id=run_id, kind=kind, error="股票库更新任务提交失败")
        logger.exception("instrument sync enqueue failed")
        raise HTTPException(status_code=500, detail="股票库更新任务提交失败，请稍后重试") from exc
    return {
        "message": "股票库更新任务已提交",
        "run_id": run_id,
        "task_id": int(task.id),
        "status": sync_status.get(run_id=run_id),
    }


@router.get("/instruments/sync/status")
def get_instrument_sync_status(
    run_id: str | None = Query(default=None, max_length=64, pattern=r"^[A-Za-z0-9_-]*$"),
):
    return sync_status.get(run_id=run_id)


@router.get("/quote/{symbol}")
def get_quote(symbol: str):
    try:
        quote = market_data.get_quote(symbol)
    except DataSourceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return quote.model_dump()


@router.get("/kline/{symbol}")
def get_kline(
    symbol: str,
    period: str = Query("daily", pattern="^(daily|1m|5m|15m)$"),
    limit: int = Query(120, ge=1, le=250),
):
    try:
        bars = (
            market_data.get_daily_bars(symbol, limit=limit)
            if period == "daily"
            else market_data.get_intraday_bars(symbol, period=period, limit=limit)
        )
    except DataSourceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"symbol": symbol, "period": period, "bars": [bar.model_dump() for bar in bars]}


@router.get("/instruments/{symbol}/rules")
def get_rules(symbol: str, db: Session = Depends(get_db)):
    instrument = market_data.get_instrument(db, symbol)
    rule = rule_service.get_or_create_rule(db, instrument)
    return rule.model_dump()


@router.get("/instruments/{symbol}/sector")
def get_sector(symbol: str, db: Session = Depends(get_db)):
    instrument = market_data.get_instrument(db, symbol)
    bars = market_data.get_intraday_bars(symbol, period="15m", limit=160)
    sector = market_data.get_sector_snapshot(instrument, bars)
    return sector.model_dump()


@router.get("/instruments/{symbol}/events")
def get_events(symbol: str, db: Session = Depends(get_db)):
    quote = market_data.get_quote(symbol)
    events = market_data.get_market_events(db, symbol, quote)
    return {"symbol": symbol, "events": [event.model_dump() for event in events]}
