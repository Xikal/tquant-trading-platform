from __future__ import annotations

import json
from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import AppSettings
from app.models.base import Base
from app.models.data_quality_entities import DataQualitySnapshot, DataRepairAudit


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
