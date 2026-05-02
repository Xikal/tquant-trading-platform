from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.market_data import DataSourceError, MarketDataService
from app.services.market_rules import MarketRuleService

router = APIRouter()
market_data = MarketDataService()
rule_service = MarketRuleService()


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
            pass
    items = market_data.search_instruments(db, keyword=keyword, kind=kind, page=page, page_size=page_size)
    total = market_data.get_total_instruments(db, kind=kind)
    return {"items": [item.model_dump() for item in items], "page": page, "page_size": page_size, "total": total}


@router.post("/instruments/sync")
def sync_instruments(
    kind: str = Query("all", pattern="^(all|stock|etf)$"),
    db: Session = Depends(get_db),
):
    try:
        result = market_data.sync_instruments(db, kind)
    except DataSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "同步完成", "result": result}


@router.get("/quote/{symbol}")
def get_quote(symbol: str):
    try:
        quote = market_data.get_quote(symbol)
    except DataSourceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return quote.model_dump()


@router.get("/kline/{symbol}")
def get_kline(symbol: str, period: str = Query("5m", pattern="^(1m|5m|15m)$"), limit: int = 240):
    try:
        bars = market_data.get_intraday_bars(symbol, period=period, limit=limit)
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
