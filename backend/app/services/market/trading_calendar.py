from __future__ import annotations

from datetime import date, timedelta
import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.entities import MarketCalendarDate


logger = logging.getLogger(__name__)


_KNOWN_CN_MARKET_HOLIDAYS = {
    # 2025
    date(2025, 1, 1),
    *[date(2025, 1, day) for day in range(28, 32)],
    *[date(2025, 2, day) for day in range(1, 5)],
    *[date(2025, 4, day) for day in range(4, 7)],
    *[date(2025, 5, day) for day in range(1, 6)],
    *[date(2025, 5, day) for day in range(31, 32)],
    date(2025, 6, 2),
    *[date(2025, 10, day) for day in range(1, 9)],
    # 2026
    date(2026, 1, 1),
    *[date(2026, 2, day) for day in range(16, 23)],
    *[date(2026, 4, day) for day in range(4, 7)],
    *[date(2026, 5, day) for day in range(1, 6)],
    *[date(2026, 6, day) for day in range(19, 22)],
    *[date(2026, 9, day) for day in range(25, 28)],
    *[date(2026, 10, day) for day in range(1, 8)],
    # 2027
    date(2027, 1, 1),
    *[date(2027, 2, day) for day in range(5, 12)],
    *[date(2027, 4, day) for day in range(3, 6)],
    *[date(2027, 5, day) for day in range(1, 6)],
    *[date(2027, 6, day) for day in range(9, 12)],
    *[date(2027, 9, day) for day in range(22, 25)],
    *[date(2027, 10, day) for day in range(1, 8)],
}


def is_a_share_trading_day(value: date) -> bool:
    stored = _stored_trading_day(value)
    if stored is not None:
        return stored
    return _fallback_is_a_share_trading_day(value)


def next_a_share_trading_day(value: date) -> date:
    stored = _stored_adjacent_trading_day(value, direction="next")
    if stored is not None:
        return stored
    next_day = value + timedelta(days=1)
    while not _fallback_is_a_share_trading_day(next_day):
        next_day += timedelta(days=1)
    return next_day


def last_a_share_trading_day(value: date | None = None) -> date:
    current = value or date.today()
    stored = _stored_adjacent_trading_day(current + timedelta(days=1), direction="previous")
    if stored is not None:
        return stored
    while not _fallback_is_a_share_trading_day(current):
        current -= timedelta(days=1)
    return current


def _fallback_is_a_share_trading_day(value: date) -> bool:
    if value.weekday() >= 5:
        return False
    if _is_chinese_calendar_holiday(value):
        return False
    return value not in _KNOWN_CN_MARKET_HOLIDAYS


def _stored_trading_day(value: date) -> bool | None:
    try:
        with SessionLocal() as db:
            return stored_trading_day(db, value)
    except (SQLAlchemyError, RuntimeError) as exc:
        logger.debug("market calendar lookup failed for %s: %s", value.isoformat(), exc)
        return None


def stored_trading_day(db: Session, value: date, *, market: str = "CN") -> bool | None:
    row = db.execute(
        select(MarketCalendarDate.is_trading_day).where(
            MarketCalendarDate.market == market,
            MarketCalendarDate.trade_date == value,
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return bool(row)


def resolved_trading_day(db: Session, value: date, *, market: str = "CN") -> bool:
    stored = stored_trading_day(db, value, market=market)
    if stored is not None:
        return stored
    return _fallback_is_a_share_trading_day(value)


def _stored_adjacent_trading_day(value: date, *, direction: str) -> date | None:
    try:
        with SessionLocal() as db:
            return stored_adjacent_trading_day(db, value, direction=direction)
    except (SQLAlchemyError, RuntimeError) as exc:
        logger.debug("market calendar adjacent lookup failed for %s: %s", value.isoformat(), exc)
        return None


def stored_adjacent_trading_day(
    db: Session,
    value: date,
    *,
    direction: str,
    market: str = "CN",
) -> date | None:
    if direction == "next":
        current = value + timedelta(days=1)
        step = timedelta(days=1)
    elif direction == "previous":
        current = value - timedelta(days=1)
        step = -timedelta(days=1)
    else:
        raise ValueError(f"unknown trading day direction: {direction}")
    for _ in range(370):
        if resolved_trading_day(db, current, market=market):
            return current
        current += step
    return None


def _is_chinese_calendar_holiday(value: date) -> bool:
    try:
        import chinese_calendar  # type: ignore
    except Exception:
        return False
    try:
        return bool(chinese_calendar.is_holiday(value))
    except Exception:
        return False
