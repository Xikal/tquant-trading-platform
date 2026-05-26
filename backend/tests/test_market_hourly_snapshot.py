from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.timezone import BEIJING_TZ
from app.models.base import Base
from app.models.entities import MarketPulseEvent, SystemSetting
from app.models.schemas import QuoteSnapshot
from app.services.market import hourly_snapshot
from app.services.market.hourly_snapshot import (
    HourlyAllMarketSnapshotService,
    hourly_all_market_snapshot_bucket,
    hourly_all_market_snapshot_due,
    latest_hourly_all_market_snapshot,
)


def _session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def _quote(symbol: str, change_pct: float) -> QuoteSnapshot:
    return QuoteSnapshot(
        symbol=symbol,
        name=symbol,
        market="SH",
        instrument_type="stock",
        last_price=10.0,
        change_pct=change_pct,
        change_amount=change_pct / 10,
        open_price=9.8,
        high_price=10.2,
        low_price=9.7,
        prev_close=9.9,
        volume=1000,
        amount=10000,
        timestamp="2026-05-25 10:30:00",
        data_source="test",
    )


def test_hourly_all_market_snapshot_due_respects_a_share_slots(monkeypatch) -> None:
    monkeypatch.setattr(hourly_snapshot, "is_a_share_trading_day", lambda _date: True)

    assert hourly_all_market_snapshot_due(datetime(2026, 5, 25, 10, 30, tzinfo=BEIJING_TZ)) is True
    assert hourly_all_market_snapshot_due(datetime(2026, 5, 25, 10, 34, tzinfo=BEIJING_TZ)) is True
    assert hourly_all_market_snapshot_due(datetime(2026, 5, 25, 10, 35, tzinfo=BEIJING_TZ)) is False
    assert hourly_all_market_snapshot_due(datetime(2026, 5, 25, 12, 0, tzinfo=BEIJING_TZ)) is False

    monkeypatch.setattr(hourly_snapshot, "is_a_share_trading_day", lambda _date: False)
    assert hourly_all_market_snapshot_due(datetime(2026, 5, 24, 10, 30, tzinfo=BEIJING_TZ)) is False


def test_hourly_all_market_snapshot_bucket_uses_slot() -> None:
    assert hourly_all_market_snapshot_bucket(datetime(2026, 5, 25, 13, 3, tzinfo=BEIJING_TZ)) == "202605251300"
    assert hourly_all_market_snapshot_bucket(datetime(2026, 5, 25, 12, 45, tzinfo=BEIJING_TZ)) == "2026052512"


def test_hourly_all_market_snapshot_refresh_stores_strength_payload() -> None:
    db = _session()
    market = SimpleNamespace(
        get_stock_spot_snapshot_map=lambda force_refresh: {
            "600000": _quote("600000", 4.2),
            "000001": _quote("000001", 0.8),
            "000002": _quote("000002", -3.5),
        }
    )

    payload = HourlyAllMarketSnapshotService(db, market).refresh(reason="test")
    state = latest_hourly_all_market_snapshot(db)
    row = db.query(SystemSetting).filter(SystemSetting.key == hourly_snapshot.SETTING_KEY).one()
    pulse_count = db.query(MarketPulseEvent).count()

    assert payload["ok"] is True
    assert payload["snapshot_count"] == 3
    assert payload["stock_up_ratio"] == 0.6667
    assert payload["strong_count"] == 1
    assert payload["weak_count"] == 1
    assert state["reason"] == "test"
    assert row.value
    assert pulse_count == 1


def test_hourly_all_market_snapshot_refresh_does_not_overwrite_slot_with_empty_payload(monkeypatch) -> None:
    db = _session()
    valid_market = SimpleNamespace(
        get_stock_spot_snapshot_map=lambda force_refresh: {
            "600000": _quote("600000", 4.2),
            "000001": _quote("000001", -1.0),
        }
    )
    empty_market = SimpleNamespace(get_stock_spot_snapshot_map=lambda force_refresh: {})

    monkeypatch.setattr(
        hourly_snapshot,
        "beijing_now",
        lambda: datetime(2026, 5, 25, 15, 0, tzinfo=BEIJING_TZ),
    )
    monkeypatch.setattr(hourly_snapshot, "beijing_now_string", lambda: "2026-05-25 15:00:00")
    HourlyAllMarketSnapshotService(db, valid_market).refresh(reason="test")

    monkeypatch.setattr(
        hourly_snapshot,
        "beijing_now",
        lambda: datetime(2026, 5, 25, 15, 4, tzinfo=BEIJING_TZ),
    )
    monkeypatch.setattr(hourly_snapshot, "beijing_now_string", lambda: "2026-05-25 15:04:00")
    HourlyAllMarketSnapshotService(db, empty_market).refresh(reason="test")

    state = latest_hourly_all_market_snapshot(db)

    assert state["ok"] is True
    assert state["snapshot_count"] == 2
    assert state["updated_at"] == "2026-05-25 15:00:00"
