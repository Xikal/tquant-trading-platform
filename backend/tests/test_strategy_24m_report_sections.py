from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import DailyBarSnapshot, MinuteBarSnapshot
from scripts.strategy_24m_report_sections import etf_t0_section, production_conclusion


def test_etf_t0_section_rejects_short_near_end_minute_window() -> None:
    db = _session()
    db.add(_daily("2026-04-27", "000001"))
    db.add(_daily("2026-04-28", "000001"))
    db.add(_minute("510300", "2026-04-28"))
    db.commit()

    section = etf_t0_section(db, start="2026-04-27", end="2026-04-28")
    profile = next(item for item in section["reports"] if item["symbol"] == "510300")
    conclusion = production_conclusion(
        strategies=[],
        etf_t0=section,
        sector_etf_t0={"status": "shadow_observation_completed"},
        smart_t={"status": "daily_proxy_completed"},
        coverage={"status": "complete"},
    )

    assert section["status"] == "partial_minute_coverage"
    assert section["expected_trade_day_count"] == 2
    assert section["accepted_symbol_count"] == 0
    assert profile["status"] == "insufficient_window_minute_coverage"
    assert profile["trade_day_coverage_pct"] == 50.0
    assert conclusion["etf_t0_acceptance"] is False
    assert conclusion["production_ready"] is False


def _session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def _daily(trade_date: str, symbol: str) -> DailyBarSnapshot:
    return DailyBarSnapshot(
        symbol=symbol,
        market="CN",
        instrument_type="stock",
        trade_date=trade_date,
        open_price=10,
        close_price=10.2,
        high_price=10.5,
        low_price=9.8,
        volume=1000,
        amount=10000,
        pct_chg=2,
    )


def _minute(symbol: str, trade_date: str) -> MinuteBarSnapshot:
    return MinuteBarSnapshot(
        symbol=symbol,
        market="SH",
        instrument_type="etf",
        bar_period="5m",
        trade_date=trade_date,
        bar_timestamp=f"{trade_date} 09:35",
        open_price=4.0,
        high_price=4.02,
        low_price=3.98,
        close_price=4.01,
        volume=1000,
        amount=4000,
        source="sina.kline",
        data_quality="fresh",
    )
