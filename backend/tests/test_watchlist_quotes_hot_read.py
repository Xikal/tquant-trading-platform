from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import watchlist
from app.models.base import Base
from app.models.entities import UserWatchlist
from app.models.schema_defs.common import QuoteSnapshot


def test_watchlist_quotes_uses_hot_read_quote_cache(monkeypatch):
    db = _db()
    db.add(UserWatchlist(user_id=7, symbol="000001", name="平安银行"))
    db.commit()
    monkeypatch.setattr(watchlist, "_refresh_user_watchlist_t1", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        watchlist,
        "read_local_quote_snapshots",
        lambda symbols: {"000001": _quote("000001", last_price=10.2)},
    )
    monkeypatch.setattr(
        watchlist,
        "load_go_intraday_latest",
        lambda _symbols: (_ for _ in ()).throw(AssertionError("cache hit must not call go intraday")),
    )

    result = watchlist.watchlist_quotes(
        current_user=SimpleNamespace(id=7),
        db=db,
    )

    assert result[0]["symbol"] == "000001"
    assert result[0]["quote"]["last_price"] == 10.2
    assert result[0]["error"] is None


def test_watchlist_quotes_returns_default_snapshot_when_hot_sources_fail(monkeypatch):
    db = _db()
    db.add(UserWatchlist(user_id=7, symbol="000002", name="万科A"))
    db.commit()
    monkeypatch.setattr(watchlist, "_refresh_user_watchlist_t1", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(watchlist, "read_local_quote_snapshots", lambda _symbols: {})
    monkeypatch.setattr(
        watchlist,
        "load_go_intraday_latest",
        lambda _symbols: (_ for _ in ()).throw(RuntimeError("go intraday down")),
    )
    monkeypatch.setattr(
        watchlist,
        "load_go_market_read_quotes",
        lambda _symbols: (_ for _ in ()).throw(RuntimeError("market read down")),
    )

    result = watchlist.watchlist_quotes(
        current_user=SimpleNamespace(id=7),
        db=db,
    )

    assert result[0]["symbol"] == "000002"
    assert result[0]["quote"]["last_price"] == 0.0
    assert result[0]["error"] == "实时行情暂不可用，已回退默认快照。"


def _quote(symbol: str, *, last_price: float) -> QuoteSnapshot:
    return QuoteSnapshot(
        symbol=symbol,
        name=symbol,
        market="SZ",
        instrument_type="stock",
        last_price=last_price,
        change_pct=1.0,
        change_amount=0.1,
        open_price=10.0,
        high_price=10.3,
        low_price=9.9,
        prev_close=10.1,
        volume=1000,
        amount=10000,
        timestamp="2026-06-05 15:00:00",
        data_source="local_quote_cache",
        source_quality="fresh",
    )


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return Session()
