from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import DailyBarSnapshot, Instrument
from app.services.quant.runtime_parameters import get_market_sector_etf_t0
from app.services.sector_etf_t0 import resolve_sector_etf_proxy


def sector_relative_strength_from_etf_proxy(
    db: Session,
    *,
    symbol: str,
    rows: list[DailyBarSnapshot],
) -> dict[str, float]:
    """Compare stock momentum with its industry ETF proxy.

    The ML sequence feature should represent sector-relative strength without
    repeatedly scanning peer stocks. ETF proxy bars are local daily snapshots;
    missing proxy data is surfaced as NaN so downstream training can treat it as
    unavailable rather than a neutral strong/weak signal.
    """

    empty = {
        "sector_relative_strength_5d": math.nan,
        "sector_relative_strength_10d": math.nan,
    }
    if len(rows) < 11:
        return empty
    sector = _sector_for_symbol(db, symbol)
    proxy = _resolve_proxy(sector)
    if proxy is None or proxy.symbol == symbol:
        return empty

    trade_dates = [str(row.trade_date) for row in rows[-11:]]
    proxy_rows = (
        db.execute(
            select(DailyBarSnapshot)
            .where(DailyBarSnapshot.symbol == proxy.symbol)
            .where(DailyBarSnapshot.trade_date.in_(trade_dates))
        )
        .scalars()
        .all()
    )
    own_closes = _close_by_date(rows)
    proxy_closes = _close_by_date(proxy_rows)

    return {
        "sector_relative_strength_5d": _relative_momentum(own_closes, proxy_closes, trade_dates, 5),
        "sector_relative_strength_10d": _relative_momentum(own_closes, proxy_closes, trade_dates, 10),
    }


def _sector_for_symbol(db: Session, symbol: str) -> str:
    instrument = db.execute(select(Instrument).where(Instrument.symbol == symbol)).scalar_one_or_none()
    return str(instrument.sector_name or "").strip() if instrument is not None else ""


def _resolve_proxy(sector: str):
    try:
        params = get_market_sector_etf_t0()
    except Exception:
        params = {}
    return resolve_sector_etf_proxy(sector, params=params)


def _close_by_date(rows: list[DailyBarSnapshot]) -> dict[str, float]:
    result: dict[str, float] = {}
    for row in rows:
        close = float(row.close_price or 0.0)
        if close > 0:
            result[str(row.trade_date)] = close
    return result


def _relative_momentum(
    own_closes: dict[str, float],
    proxy_closes: dict[str, float],
    trade_dates: list[str],
    days: int,
) -> float:
    if len(trade_dates) <= days:
        return math.nan
    start_date = trade_dates[-days - 1]
    end_date = trade_dates[-1]
    own_start = own_closes.get(start_date, 0.0)
    own_end = own_closes.get(end_date, 0.0)
    proxy_start = proxy_closes.get(start_date, 0.0)
    proxy_end = proxy_closes.get(end_date, 0.0)
    if own_start <= 0 or own_end <= 0 or proxy_start <= 0 or proxy_end <= 0:
        return math.nan
    own_momentum = (own_end / own_start - 1.0) * 100.0
    proxy_momentum = (proxy_end / proxy_start - 1.0) * 100.0
    return round(own_momentum - proxy_momentum, 4)
