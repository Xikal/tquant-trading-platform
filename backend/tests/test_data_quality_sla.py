from __future__ import annotations

import json
from datetime import date, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import AppSettings
from app.models.base import Base
from app.models.data_quality_entities import DataQualitySnapshot, DataRepairAudit
from app.models.entities import DailyBarSnapshot, Instrument, MinuteBarSnapshot, TickTradeSnapshot
from app.services.data_quality.sla import compute_dataset_sla


def test_schema_roundtrip() -> None:
    settings = AppSettings()
    assert settings.data_quality_sla_enabled is True
    assert settings.data_repair_auto_enabled is False

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)

    with Session() as db:
        snapshot = DataQualitySnapshot(
            dataset_key="daily_bars",
            as_of_date=date(2026, 5, 29),
            scope="production_universe",
            expected_days=480,
            actual_days=477,
            missing_days=3,
            invalid_rows=1,
            duplicate_rows=0,
            stale=False,
            coverage_pct=99.37,
            status="fail",
            blockers_json=json.dumps(["daily_bars_invalid_ohlc"], ensure_ascii=False),
        )
        audit = DataRepairAudit(
            repair_id="repair-20260529-0001",
            dataset_key="daily_bars",
            reason="daily_bars_invalid_ohlc",
            detected_rows_json=json.dumps([{"symbol": "000001", "trade_date": "2026-05-29"}]),
            backup_path="/tmp/daily_bars-backup.json",
            refetch_result="empty",
            deleted_rows_json="[]",
            fabricated=False,
            operator="pytest",
        )
        db.add_all([snapshot, audit])
        db.commit()

    with Session() as db:
        stored_snapshot = db.execute(select(DataQualitySnapshot)).scalar_one()
        stored_audit = db.execute(select(DataRepairAudit)).scalar_one()

    assert stored_snapshot.dataset_key == "daily_bars"
    assert stored_snapshot.scope == "production_universe"
    assert stored_snapshot.status == "fail"
    assert json.loads(stored_snapshot.blockers_json) == ["daily_bars_invalid_ohlc"]
    assert stored_audit.fabricated is False
    assert stored_audit.repair_id == "repair-20260529-0001"


def test_daily_bars_sla_fails_on_invalid_ohlc_and_records_missing_days() -> None:
    db = _session()
    try:
        for offset in range(7):
            trade_date = date(2026, 5, 18) + timedelta(days=offset)
            if trade_date.weekday() >= 5 or trade_date in {date(2026, 5, 19), date(2026, 5, 20), date(2026, 5, 21)}:
                continue
            db.add(_daily_bar("000001", trade_date))
        db.add(_daily_bar("000001", date(2026, 5, 25), open_price=0.0))
        db.commit()

        snapshot = compute_dataset_sla(
            db,
            dataset_key="daily_bars",
            scope="all",
            as_of=date(2026, 5, 25),
            start_date=date(2026, 5, 18),
            expected_days=6,
        )

        assert snapshot.status == "fail"
        assert snapshot.missing_days == 3
        assert snapshot.invalid_rows == 1
        assert "daily_bars_invalid_ohlc" in json.loads(snapshot.blockers_json)
        stored = db.execute(select(DataQualitySnapshot)).scalar_one()
        assert stored.id == snapshot.id
    finally:
        db.close()


def test_daily_bars_sla_production_universe_excludes_research_only_boards() -> None:
    db = _session()
    try:
        for symbol in ("600000", "300001", "688001", "000002", "000003"):
            db.add(
                Instrument(
                    symbol=symbol,
                    name={
                        "600000": "浦发银行",
                        "300001": "创业成长",
                        "688001": "科创芯片",
                        "000002": "*ST测试",
                        "000003": "退市测试",
                    }[symbol],
                    market="CN",
                    instrument_type="stock",
                    is_st=symbol == "000002",
                    status="delisted" if symbol == "000003" else "active",
                )
            )
            db.add(_daily_bar(symbol, date(2026, 5, 25)))
        db.commit()

        snapshot = compute_dataset_sla(
            db,
            dataset_key="daily_bars",
            scope="production_universe",
            as_of=date(2026, 5, 25),
            start_date=date(2026, 5, 25),
            expected_days=1,
        )

        assert snapshot.status == "ok"
        assert snapshot.actual_days == 1
        assert snapshot.invalid_rows == 0
        assert snapshot.missing_days == 0
    finally:
        db.close()


def test_minute_and_tick_sla_mark_unavailable_without_fake_scores() -> None:
    db = _session()
    try:
        db.add(
            MinuteBarSnapshot(
                symbol="510300",
                market="CN",
                instrument_type="etf",
                bar_period="5m",
                trade_date=date(2026, 5, 25),
                bar_timestamp="2026-05-25 09:35",
                source="unit-test",
            )
        )
        db.add(
            TickTradeSnapshot(
                symbol="510300",
                market="CN",
                instrument_type="etf",
                trade_date=date(2026, 5, 25),
                trade_timestamp="2026-05-25 09:35:00",
                price=4.0,
                volume=100.0,
                source="unit-test",
            )
        )
        db.commit()

        minute_snapshot = compute_dataset_sla(
            db,
            dataset_key="minute_bars",
            scope="all",
            as_of=date(2026, 5, 26),
            start_date=date(2026, 5, 25),
            expected_days=2,
        )
        tick_snapshot = compute_dataset_sla(
            db,
            dataset_key="tick_trades",
            scope="all",
            as_of=date(2026, 5, 26),
            start_date=date(2026, 5, 25),
            expected_days=2,
        )

        assert minute_snapshot.status == "unavailable"
        assert tick_snapshot.status == "unavailable"
        assert minute_snapshot.missing_days == 1
        assert tick_snapshot.missing_days == 1
        assert "minute_bars_unavailable" in json.loads(minute_snapshot.blockers_json)
        assert "tick_trades_unavailable" in json.loads(tick_snapshot.blockers_json)
    finally:
        db.close()


def _session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    return Session()


def _daily_bar(
    symbol: str,
    trade_date: date,
    *,
    open_price: float = 10.0,
    high_price: float = 10.5,
    low_price: float = 9.8,
    close_price: float = 10.2,
) -> DailyBarSnapshot:
    return DailyBarSnapshot(
        symbol=symbol,
        market="CN",
        instrument_type="stock",
        trade_date=trade_date,
        open_price=open_price,
        close_price=close_price,
        high_price=high_price,
        low_price=low_price,
        volume=1000,
        amount=10000,
        pct_chg=1.0,
        source="unit-test",
        data_quality="ok",
    )
