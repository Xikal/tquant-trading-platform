from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import DailyBarSnapshot, Instrument
from backend.scripts.backfill_daily_limit_prices import backfill_daily_limit_prices, derive_limit_prices


def test_derive_limit_prices_covers_a_share_boards_and_st() -> None:
    assert derive_limit_prices(symbol="600000", pre_close=10, trade_date="2026-04-28").limit_up_price == 11.0
    assert derive_limit_prices(symbol="000001", pre_close=10, trade_date="2026-04-28", is_st=True).limit_up_price == 10.5
    assert derive_limit_prices(symbol="688001", pre_close=10, trade_date="2026-04-28").limit_down_price == 8.0
    assert derive_limit_prices(symbol="300001", pre_close=10, trade_date="2020-08-21").limit_up_price == 11.0
    assert derive_limit_prices(symbol="300001", pre_close=10, trade_date="2020-08-24").limit_up_price == 12.0
    assert derive_limit_prices(symbol="920001", pre_close=10, trade_date="2026-04-28").limit_down_price == 7.0


def test_derive_limit_prices_skips_listing_exempt_and_fund_like_rows() -> None:
    assert derive_limit_prices(symbol="600000", pre_close=10, trade_date="2026-04-28", listing_date="2026-04-28") is None
    assert derive_limit_prices(symbol="510300", pre_close=4, trade_date="2026-04-28", instrument_type="etf") is None


def test_backfill_daily_limit_prices_updates_missing_fields_and_audit_report() -> None:
    db = _session()
    db.add(Instrument(symbol="600000", name="浦发银行", market="SH", instrument_type="stock", listing_date="1999-11-10", status="active"))
    db.add(Instrument(symbol="688001", name="华兴源创", market="SH", instrument_type="stock", listing_date="2019-07-22", status="active"))
    db.add(_daily("600000", "2026-04-28", pre_close=10))
    db.add(_daily("688001", "2026-04-28", pre_close=20))
    db.add(_daily("600000", "2026-04-29", pre_close=0))
    db.commit()

    report = backfill_daily_limit_prices(db, start_date="2026-04-28", end_date="2026-04-29")
    db.commit()

    main = db.query(DailyBarSnapshot).filter_by(symbol="600000", trade_date="2026-04-28").one()
    star = db.query(DailyBarSnapshot).filter_by(symbol="688001").one()

    assert report["updated_rows"] == 2
    assert report["skipped_no_pre_close"] == 1
    assert report["ratio_counts"] == {"10.0%": 1, "20.0%": 1}
    assert main.limit_up_price == 11.0
    assert main.limit_down_price == 9.0
    assert "limit_rules_v1" in main.source
    assert main.data_quality == "verified"
    assert star.limit_up_price == 24.0
    assert len(main.checksum) == 64


def test_backfill_daily_limit_prices_skips_recent_listing_without_hard_fill() -> None:
    db = _session()
    db.add(Instrument(symbol="301999", name="测试新股", market="SZ", instrument_type="stock", listing_date="2026-04-25", status="active"))
    db.add(_daily("301999", "2026-04-28", pre_close=10))
    db.commit()

    report = backfill_daily_limit_prices(db, start_date="2026-04-28", end_date="2026-04-28")
    row = db.query(DailyBarSnapshot).filter_by(symbol="301999").one()

    assert report["updated_rows"] == 0
    assert report["skipped_listing_exempt"] == 1
    assert row.limit_up_price == 0
    assert row.limit_down_price == 0


def test_backfill_daily_limit_prices_treats_null_limit_fields_as_missing() -> None:
    db = _session()
    db.add(Instrument(symbol="000001", name="平安银行", market="SZ", instrument_type="stock", listing_date="1991-04-03", status="active"))
    db.add(_daily("000001", "2026-04-28", pre_close=10))
    db.commit()
    db.query(DailyBarSnapshot).filter_by(symbol="000001").update({"limit_up_price": None, "limit_down_price": None})
    db.commit()

    report = backfill_daily_limit_prices(db, start_date="2026-04-28", end_date="2026-04-28")
    row = db.query(DailyBarSnapshot).filter_by(symbol="000001").one()

    assert report["updated_rows"] == 1
    assert row.limit_up_price == 11.0
    assert row.limit_down_price == 9.0


def test_backfill_daily_limit_prices_can_derive_pre_close_from_previous_real_close() -> None:
    db = _session()
    db.add(Instrument(symbol="600000", name="浦发银行", market="SH", instrument_type="stock", listing_date="1999-11-10", status="active"))
    db.add(_daily("600000", "2026-04-27", pre_close=0, close_price=10.0))
    db.add(_daily("600000", "2026-04-28", pre_close=0, close_price=10.4))
    db.commit()

    report = backfill_daily_limit_prices(db, start_date="2026-04-27", end_date="2026-04-28", derive_pre_close=True)
    row = db.query(DailyBarSnapshot).filter_by(symbol="600000", trade_date="2026-04-28").one()

    assert report["updated_rows"] == 1
    assert report["derived_pre_close_rows"] == 1
    assert report["skipped_no_previous_close"] == 1
    assert row.pre_close == 10.0
    assert row.limit_up_price == 11.0
    assert row.limit_down_price == 9.0


def _session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def _daily(symbol: str, trade_date: str, *, pre_close: float, close_price: float | None = None) -> DailyBarSnapshot:
    close = pre_close if close_price is None else close_price
    return DailyBarSnapshot(
        symbol=symbol,
        market="CN",
        instrument_type="stock",
        trade_date=trade_date,
        open_price=pre_close,
        close_price=close,
        high_price=max(pre_close, close),
        low_price=min(value for value in (pre_close, close) if value > 0) if pre_close > 0 or close > 0 else 0,
        volume=1000,
        amount=10000,
        pct_chg=0,
        pre_close=pre_close,
        source="akshare.stock_zh_a_hist",
        adjusted_mode="qfq",
        data_quality="partial_metadata",
    )
