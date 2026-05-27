from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.timezone import beijing_now
from app.models.base import Base
from app.models.entities import MarketPulseEvent
from app.services.market.pulse_cache import latest_pulse_or_placeholder


def _session():
    engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    return Session()


def test_latest_pulse_or_placeholder_returns_stored_event():
    db = _session()
    try:
        db.add(
            MarketPulseEvent(
                trade_date="2026-05-27",
                pulse_level="defensive",
                data_quality="partial",
                pulse_text="市场偏弱，先防守。",
                suggested_action="少交易，等确认。",
                payload_json='{"updated_at":"2026-05-27 10:30:00","data_quality":"partial","pulse_level":"defensive","pulse_text":"市场偏弱，先防守。","suggested_action":"少交易，等确认。","partial_errors":[]}',
                created_at=beijing_now().replace(tzinfo=None),
            )
        )
        db.commit()

        pulse, needs_refresh = latest_pulse_or_placeholder(db, trade_date="2026-05-27")

        assert pulse.pulse_level == "defensive"
        assert pulse.pulse_text == "市场偏弱，先防守。"
        assert needs_refresh is False
    finally:
        db.close()


def test_latest_pulse_or_placeholder_marks_stale_event():
    db = _session()
    try:
        db.add(
            MarketPulseEvent(
                trade_date="2026-05-27",
                pulse_level="repair",
                data_quality="fresh",
                pulse_text="市场修复。",
                suggested_action="小仓确认。",
                payload_json='{"updated_at":"2026-05-27 10:30:00","data_quality":"fresh","pulse_level":"repair","pulse_text":"市场修复。","suggested_action":"小仓确认。"}',
                created_at=(datetime.now() - timedelta(minutes=10)),
            )
        )
        db.commit()

        pulse, needs_refresh = latest_pulse_or_placeholder(db, trade_date="2026-05-27", fresh_seconds=60)

        assert needs_refresh is True
        assert pulse.data_quality == "stale"
        assert any(item["source"] == "pulse_snapshot" for item in pulse.partial_errors)
    finally:
        db.close()


def test_latest_pulse_or_placeholder_queues_refresh_when_missing():
    db = _session()
    try:
        pulse, needs_refresh = latest_pulse_or_placeholder(db, trade_date="2026-05-27")

        assert pulse.data_quality == "unavailable"
        assert needs_refresh is True
        assert pulse.partial_errors
    finally:
        db.close()

