from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import intraday
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.base import Base
from app.models.entities import MinuteBarSnapshot
from app.services.decision_context.intraday_entry import (
    IntradayEntryInput,
    evaluate_intraday_entry,
    refresh_intraday_entry_snapshots,
)


def test_intraday_entry_waits_when_price_is_chasing_far_above_zone() -> None:
    result = evaluate_intraday_entry(
        IntradayEntryInput(
            symbol="600000",
            strategy_key="first_board",
            trade_date=date(2026, 5, 31),
            entry_zone_low=9.6,
            entry_zone_high=10.0,
            support_price=9.6,
            latest_price=10.8,
            minute_bars=[
                _minute("600000", "2026-05-31", "2026-05-31 09:30", open_price=10.5, close=10.6, high=10.7, low=10.4),
                _minute("600000", "2026-05-31", "2026-05-31 09:31", open_price=10.6, close=10.7, high=10.8, low=10.5),
                _minute("600000", "2026-05-31", "2026-05-31 09:32", open_price=10.7, close=10.8, high=10.9, low=10.6),
                _minute("600000", "2026-05-31", "2026-05-31 09:33", open_price=10.8, close=10.82, high=10.92, low=10.7),
                _minute("600000", "2026-05-31", "2026-05-31 09:34", open_price=10.82, close=10.8, high=10.9, low=10.72),
            ],
        )
    )

    assert result.decision == "wait"
    assert result.production_score_delta == 0.0
    assert result.data_quality == "ok"
    assert result.entry_zone_high == 10.0
    assert result.vwap_distance_pct is not None
    assert any("追高" in reason or "回踩" in reason for reason in result.reasons)


def test_intraday_entry_marks_no_data_and_never_adds_production_score_without_minutes() -> None:
    result = evaluate_intraday_entry(
        IntradayEntryInput(
            symbol="600000",
            strategy_key="first_board",
            trade_date=date(2026, 5, 31),
            entry_zone_low=9.6,
            entry_zone_high=10.0,
            latest_price=9.8,
            minute_bars=[],
        )
    )

    assert result.decision == "no_data"
    assert result.data_quality == "missing"
    assert result.production_score_delta == 0.0
    assert any("分钟" in reason for reason in result.reasons)


def test_refresh_intraday_entry_snapshots_returns_explicit_no_data_for_missing_minutes() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)

    with Session() as db:
        result = refresh_intraday_entry_snapshots(
            db,
            symbols=["600000"],
            trade_date=date(2026, 5, 31),
            entry_context={"600000": {"strategy_key": "first_board", "entry_zone_low": 9.6, "entry_zone_high": 10.0}},
        )

    assert result["ok"] is True
    assert result["status"] == "no_data"
    assert result["items"][0]["decision"] == "no_data"
    assert result["items"][0]["production_score_delta"] == 0.0


def test_intraday_entry_api_returns_decision_fields() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    app = FastAPI()
    app.include_router(intraday.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: object()

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    response = client.post(
        "/api/intraday/entry-decision",
        json={
            "symbol": "600000",
            "strategy_key": "first_board",
            "trade_date": "2026-05-31",
            "entry_zone_low": 9.6,
            "entry_zone_high": 10.0,
            "latest_price": 9.8,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "600000"
    assert body["intraday_entry_decision"] == "no_data"
    assert body["data_quality"] == "missing"
    assert body["production_score_delta"] == 0.0
    assert "分钟" in body["confirmation_text"]


def _minute(
    symbol: str,
    trade_date: str,
    timestamp: str,
    *,
    open_price: float,
    close: float,
    high: float,
    low: float,
    volume: float = 1000,
) -> MinuteBarSnapshot:
    return MinuteBarSnapshot(
        symbol=symbol,
        trade_date=trade_date,
        bar_timestamp=timestamp,
        open_price=open_price,
        close_price=close,
        high_price=high,
        low_price=low,
        last_price=close,
        volume=volume,
        amount=close * volume,
        bar_period="1m",
        data_quality="ok",
        source="unit-test",
    )
