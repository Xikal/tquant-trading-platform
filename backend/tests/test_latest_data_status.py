from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import DailyBarSnapshot, LowBuyScanSnapshot
from app.services import latest_data_status as status_module


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def test_daily_bar_freshness_uses_beijing_post_close_cutoff() -> None:
    db = _db()
    _seed_daily_bars(db, fetch_time="2026-06-03T13:51:11")

    freshness = status_module.daily_bar_freshness_status(db, "2026-06-03")

    assert freshness["daily_bar_count"] == status_module.MIN_STOCK_DAILY_BARS
    assert freshness["post_close_fetch_cutoff"] == "2026-06-03T15:01:00"
    assert freshness["post_close_daily_bar_count"] == 0
    assert freshness["daily_bar_freshness_status"] == "stale_before_post_close"


def test_publish_latest_trade_date_requires_post_close_daily_bars(monkeypatch) -> None:
    db = _db()
    monkeypatch.setattr(status_module, "expected_low_buy_trade_date", lambda _db: "2026-06-03")
    _seed_daily_bars(db, fetch_time="2026-06-03T13:51:11")
    _seed_strategy_summaries(db, "2026-06-03")
    db.commit()

    payload = status_module.publish_latest_trade_date_if_ready(db)

    assert payload["status"] == "pending"
    assert payload["published_trade_date"] == ""
    assert payload["daily_bar_count"] == status_module.MIN_STOCK_DAILY_BARS
    assert payload["post_close_daily_bar_count"] == 0
    assert payload["daily_bar_freshness_status"] == "stale_before_post_close"


def test_publish_latest_trade_date_succeeds_after_beijing_post_close_fetch(monkeypatch) -> None:
    db = _db()
    monkeypatch.setattr(status_module, "expected_low_buy_trade_date", lambda _db: "2026-06-03")
    _seed_daily_bars(db, fetch_time="2026-06-03T15:31:00")
    _seed_strategy_summaries(db, "2026-06-03")
    db.commit()

    payload = status_module.publish_latest_trade_date_if_ready(db)

    assert payload["status"] == "success"
    assert payload["published_trade_date"] == "2026-06-03"
    assert payload["post_close_daily_bar_count"] == status_module.MIN_STOCK_DAILY_BARS
    assert payload["daily_bar_freshness_status"] == "post_close_complete"


def test_expected_trade_date_uses_calendar_not_stale_local_history(monkeypatch) -> None:
    db = _db()
    _seed_daily_bars(db, trade_date=date(2026, 5, 29), fetch_time="2026-05-29T15:31:00")
    monkeypatch.setattr(
        status_module,
        "beijing_now",
        lambda: datetime(2026, 6, 6, 10, 0, 0),
    )

    payload = status_module.latest_data_status(db, strategies=[])

    assert payload["expected_trade_date"] == "2026-06-05"
    assert payload["calendar_expected_trade_date"] == "2026-06-05"
    assert payload["local_latest_trade_date"] == "2026-05-29"
    assert payload["staleness_trade_days"] >= 1
    assert payload["local_staleness_trade_days"] >= 1
    assert payload["daily_bar_count"] == 0


def test_trade_day_gap_uses_calendar_when_local_history_is_partial() -> None:
    db = _db()
    _seed_one_daily_bar(db, trade_date=date(2026, 6, 1))

    gap = status_module.trade_day_gap(db, "2026-05-29", "2026-06-05")

    assert gap == 5


def _seed_one_daily_bar(db, *, trade_date: date) -> None:  # noqa: ANN001
    db.add(
        DailyBarSnapshot(
            symbol="000001",
            trade_date=trade_date,
            close_price=10,
            pre_close=9.9,
            volume=1000,
            amount=10000,
            pct_chg=1.0,
            fetch_time=f"{trade_date.isoformat()}T15:31:00",
        )
    )
    db.commit()


def _seed_daily_bars(db, *, fetch_time: str, trade_date: date = date(2026, 6, 3)) -> None:  # noqa: ANN001
    for index in range(status_module.MIN_STOCK_DAILY_BARS):
        db.add(
            DailyBarSnapshot(
                symbol=f"{index:06d}",
                trade_date=trade_date,
                close_price=10,
                pre_close=9.9,
                volume=1000,
                amount=10000,
                pct_chg=1.0,
                fetch_time=fetch_time,
            )
        )
    db.commit()


def _seed_strategy_summaries(db, trade_date: str) -> None:  # noqa: ANN001
    for strategy in status_module.PRODUCTION_PRIORITY_STRATEGIES:
        db.add(
            LowBuyScanSnapshot(
                latest_trade_date=trade_date,
                strategy_key=strategy,
                pool_size=1,
                scanned_count=1,
                matched_count=1,
            )
        )
