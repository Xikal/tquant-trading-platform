from __future__ import annotations

from argparse import Namespace
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import MinuteBarSnapshot
from backend.scripts import backfill_etf_execution_metadata as script


def test_etf_execution_metadata_backfill_does_not_fake_spread_or_premium(monkeypatch) -> None:
    db = _session()
    monkeypatch.setattr(script, "beijing_now", lambda: datetime(2026, 4, 28, 15, 40, 0))
    db.add(
        MinuteBarSnapshot(
            symbol="510300",
            market="SH",
            instrument_type="etf",
            bar_period="5m",
            trade_date="2026-04-28",
            bar_timestamp="2026-04-28 09:35",
            open_price=4.0,
            high_price=4.1,
            low_price=3.9,
            close_price=4.05,
            volume=100,
            amount=200_000_000,
            bid_ask_spread=0.0,
            premium_discount_pct=None,
            tracking_index_symbol="",
            liquidity_tier="unknown",
            data_quality="unknown",
        )
    )
    db.commit()
    profile = script.resolve_profiles(scope="symbols", raw_symbols="510300")[0]

    results = script.backfill_execution_metadata(db, profiles=[profile], start_date="2026-04-28", end_date="2026-04-28", period="5m")
    row = db.query(MinuteBarSnapshot).filter_by(symbol="510300").one()
    report = script.build_report(
        args=Namespace(scope="symbols", symbols="510300", start_date="2026-04-28", end_date="2026-04-28", period="5m", dry_run=False),
        profiles=[profile],
        results=results,
    )

    assert row.tracking_index_symbol == "沪深300"
    assert row.liquidity_tier == "sufficient"
    assert row.bid_ask_spread == 0.0
    assert row.premium_discount_pct is None
    assert row.data_quality == "partial_metadata"
    assert row.fetch_time == "2026-04-28T15:40:00"
    assert results[0].updated_rows == 1
    assert report["status"] == "completed_with_blocking_metadata_gaps"
    assert report["totals"]["fresh_or_verified_rows"] == 0


def _session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()
