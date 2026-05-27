from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import DailyBarSnapshot, Instrument
from app.models.schemas import QuoteSnapshot
from app.services.market.local_quote_cache import LOCAL_QUOTE_FRESH_AGE_SECONDS, LOCAL_QUOTE_TTL_SECONDS
from app.services.market.service import MarketDataService
from app.services.market_quote_cache_refresh import MarketQuoteCacheRefreshService


def test_stock_spot_snapshot_persists_redis_quote_cache(monkeypatch):
    written: dict[str, object] = {}

    quote = QuoteSnapshot(
        symbol="000001",
        name="平安银行",
        market="SZ",
        instrument_type="stock",
        last_price=10.2,
        change_pct=1.2,
        change_amount=0.12,
        open_price=10.0,
        high_price=10.3,
        low_price=9.9,
        prev_close=10.08,
        volume=1000,
        amount=10200,
        timestamp="2026-05-27 10:00:00",
        data_source="eastmoney_realtime",
        source_quality="fresh",
    )

    monkeypatch.setattr("app.services.market.quotes.fetch_eastmoney_stock_spot_snapshot_map", lambda _service: {"000001": quote})
    monkeypatch.setattr("app.services.market.quotes.write_local_quote_snapshots", lambda payload: written.update(payload) or len(payload))
    service = MarketDataService()
    service._spot_snapshot_cache.clear()

    result = service.get_stock_spot_snapshot_map(force_refresh=True)

    assert result["000001"].last_price == 10.2
    assert written["000001"].data_source == "eastmoney_realtime"


def test_quote_cache_refresh_writes_daily_fallback_when_realtime_missing(monkeypatch):
    Session = _session_factory()
    with Session() as db:
        db.add(Instrument(symbol="000001", name="平安银行", market="SZ", instrument_type="stock"))
        db.add(
            DailyBarSnapshot(
                symbol="000001",
                market="SZ",
                instrument_type="stock",
                trade_date=date(2026, 5, 27),
                open_price=10.0,
                close_price=10.2,
                high_price=10.3,
                low_price=9.9,
                volume=1000,
                amount=10200,
                pct_chg=1.2,
                pre_close=10.08,
            )
        )
        db.commit()

        written: dict[str, QuoteSnapshot] = {}
        monkeypatch.setattr(
            "app.services.market_quote_cache_refresh.write_local_quote_snapshots",
            lambda payload: written.update(payload) or len(payload),
        )
        service = MarketQuoteCacheRefreshService(db)
        service._target_symbols = lambda limit: ["000001"]  # type: ignore[method-assign]
        service.market.get_quotes_batch = lambda *_args, **_kwargs: {}  # type: ignore[method-assign]

        result = service.refresh(limit=1)

        assert result["count"] == 1
        assert result["redis_written"] == 1
        assert result["missing_count"] == 0
        assert written["000001"].data_source == "mysql_daily_bar_snapshot"
        assert written["000001"].data_quality == "stale"


def test_quote_cache_ttl_policy_matches_go_market_read_fresh_window():
    assert LOCAL_QUOTE_FRESH_AGE_SECONDS <= 30
    assert LOCAL_QUOTE_TTL_SECONDS >= LOCAL_QUOTE_FRESH_AGE_SECONDS


def _session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)
