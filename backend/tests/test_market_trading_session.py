from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import MarketCalendarDate
from app.services.market.trading_calendar import stored_adjacent_trading_day, stored_trading_day
from app.services.market.trading_session import current_a_share_trading_session


def test_afternoon_close_instant_is_not_trading() -> None:
    status = current_a_share_trading_session(datetime(2026, 5, 6, 15, 0, 0))

    assert status.is_trading_day is True
    assert status.is_trading_now is False


def test_one_second_before_afternoon_close_is_trading() -> None:
    status = current_a_share_trading_session(datetime(2026, 5, 6, 14, 59, 59))

    assert status.is_trading_day is True
    assert status.is_trading_now is True


def test_market_calendar_dates_can_override_fallback_calendar() -> None:
    db = _db()
    db.add(MarketCalendarDate(market="CN", trade_date=date(2026, 6, 6), is_trading_day=True, source="test"))
    db.add(MarketCalendarDate(market="CN", trade_date=date(2026, 6, 7), is_trading_day=False, source="test"))
    db.add(MarketCalendarDate(market="CN", trade_date=date(2026, 6, 8), is_trading_day=True, source="test"))
    db.commit()

    assert stored_trading_day(db, datetime(2026, 6, 6).date()) is True
    assert stored_adjacent_trading_day(db, datetime(2026, 6, 6).date(), direction="next") == datetime(2026, 6, 8).date()


def test_partial_market_calendar_does_not_hide_fallback_adjacent_dates() -> None:
    db = _db()
    db.add(MarketCalendarDate(market="CN", trade_date=date(2026, 5, 29), is_trading_day=True, source="test"))
    db.commit()

    assert stored_adjacent_trading_day(db, date(2026, 6, 6), direction="previous") == date(2026, 6, 5)


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
