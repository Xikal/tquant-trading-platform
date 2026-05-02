import asyncio
import concurrent.futures
from datetime import datetime
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.timing import log_slow_call, monotonic_start
from app.models.entities import Instrument, User, UserWatchlist, Watchlist
from app.models.schemas import WatchlistCreate, WatchlistItemOut
from app.services.market_data import MarketDataService, guess_instrument_type, guess_market
from app.services.watchlist_signal_service import WatchlistSignalService

router = APIRouter(prefix="/watchlist")
logger = logging.getLogger(__name__)
market_data = MarketDataService()
watchlist_signal_service = WatchlistSignalService()
WATCHLIST_QUOTE_WORKERS = 10


def _fallback_quote_payload(symbol: str, name: str) -> dict:
    market = guess_market(symbol)
    instrument_type = guess_instrument_type(symbol, name)
    return {
        "symbol": symbol,
        "name": name or symbol,
        "market": market,
        "instrument_type": instrument_type,
        "last_price": 0.0,
        "change_pct": 0.0,
        "change_amount": 0.0,
        "open_price": 0.0,
        "high_price": 0.0,
        "low_price": 0.0,
        "prev_close": 0.0,
        "volume": 0.0,
        "amount": 0.0,
        "turnover_rate": None,
        "volume_ratio": None,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _fallback_rule_payload(symbol: str) -> dict:
    return {
        "symbol": symbol,
        "turnaround_mode": "t1",
        "supports_positive_t": True,
        "supports_negative_t": True,
        "same_day_sell_allowed": False,
        "requires_base_position": True,
        "notes": "行情异常时返回默认制度说明。",
    }


@router.get("")
def list_watchlist(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = _list_user_watchlist_rows(db, current_user.id)
    return [
        WatchlistItemOut(
            symbol=row.symbol,
            name=row.name,
            base_position=row.base_position,
            available_position=row.available_position,
            cost_basis=row.cost_basis,
            memo=row.memo,
            created_at=row.created_at,
        ).model_dump()
        for row in rows
    ]


@router.post("")
def upsert_watchlist(
    payload: WatchlistCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    symbol = payload.symbol.strip()
    display_name = _resolve_watchlist_name(db, symbol=symbol, provided_name=payload.name)
    row = _get_user_watchlist_row(db, current_user.id, symbol)
    if row is None:
        values = payload.model_dump()
        values["symbol"] = symbol
        values["name"] = display_name
        row = UserWatchlist(user_id=current_user.id, **values)
        db.add(row)
    else:
        row.name = display_name or row.name
        row.base_position = payload.base_position
        row.available_position = payload.available_position
        row.cost_basis = payload.cost_basis
        row.memo = payload.memo
    db.commit()
    watchlist_signal_service.ensure_background_refresh(force=True)
    return {"message": "自选股已保存", "symbol": symbol}


def _resolve_watchlist_name(db: Session, *, symbol: str, provided_name: str) -> str:
    cleaned = provided_name.strip()
    if cleaned and cleaned != symbol:
        return cleaned
    instrument = db.execute(select(Instrument).where(Instrument.symbol == symbol)).scalar_one_or_none()
    if instrument is not None and instrument.name and instrument.name != symbol:
        return instrument.name
    return "" if not cleaned else cleaned


@router.delete("/{symbol}")
def remove_watchlist(
    symbol: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _get_user_watchlist_row(db, current_user.id, symbol)
    if row is None:
        raise HTTPException(status_code=404, detail="自选股不存在")
    db.delete(row)
    db.commit()
    watchlist_signal_service.invalidate_symbol(symbol)
    watchlist_signal_service.ensure_background_refresh(force=True)
    return {"message": "已删除", "symbol": symbol}


def _watchlist_quote_item(row: Watchlist) -> dict:
    error_message = ""
    try:
        quote_payload = market_data.get_quote(row.symbol).model_dump()
    except Exception as exc:
        quote_payload = _fallback_quote_payload(row.symbol, row.name or row.symbol)
        error_message = str(exc)
    return {
        "symbol": row.symbol,
        "name": row.name or quote_payload["name"],
        "base_position": row.base_position,
        "available_position": row.available_position,
        "cost_basis": row.cost_basis,
        "memo": row.memo,
        "quote": quote_payload,
        "error": error_message or None,
    }


@router.get("/quotes")
async def watchlist_quotes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = _list_user_watchlist_rows(db, current_user.id)
    if not rows:
        return []
    max_workers = min(WATCHLIST_QUOTE_WORKERS, max(len(rows), 1))
    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        return await asyncio.gather(
            *(loop.run_in_executor(pool, _watchlist_quote_item, row) for row in rows)
        )


@router.get("/signals")
def watchlist_signals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    started_at = monotonic_start()
    try:
        rows = _list_user_watchlist_rows(db, current_user.id)
        return watchlist_signal_service.build_live_signals(db, rows)
    finally:
        log_slow_call(logger, "watchlist.signals", started_at)


def _list_user_watchlist_rows(db: Session, user_id: int) -> list[UserWatchlist]:
    return (
        db.execute(
            select(UserWatchlist)
            .where(UserWatchlist.user_id == user_id)
            .order_by(UserWatchlist.id.desc())
        )
        .scalars()
        .all()
    )


def _get_user_watchlist_row(db: Session, user_id: int, symbol: str) -> Optional[UserWatchlist]:
    return (
        db.execute(
            select(UserWatchlist).where(
                UserWatchlist.user_id == user_id,
                UserWatchlist.symbol == symbol,
            )
        )
        .scalars()
        .first()
    )
