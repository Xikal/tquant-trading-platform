from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import DailyBarSnapshot, RuntimeTask
from app.services.analytics.exporters import export_daily_bars_parquet
from app.services.analytics.manifest import load_manifest
from app.services.analytics.quality import check_daily_bars_24m_quality


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def test_quality_creates_backfill_task_when_24m_data_incomplete(tmp_path):
    db = _db()
    db.add(_bar("000001", date(2026, 5, 29)))
    db.commit()

    quality = check_daily_bars_24m_quality(
        db,
        months=24,
        end_date=date(2026, 5, 30),
        min_symbols_per_day=1,
        create_backfill_task=True,
    )

    assert quality.status == "fail"
    assert "daily_bars_start_after_required_window" in quality.blockers
    assert quality.backfill_task_id is not None
    task = db.get(RuntimeTask, quality.backfill_task_id)
    assert task is not None
    assert task.task_type == "data_backfill_24m"


def test_export_writes_parquet_and_manifest_with_failure_quality(tmp_path):
    db = _db()
    for offset in range(3):
        db.add(_bar("000001", date(2026, 5, 27) + timedelta(days=offset)))
    db.commit()

    manifest = export_daily_bars_parquet(
        db,
        months=24,
        end_date=date(2026, 5, 30),
        output_root=tmp_path,
        create_backfill_task=True,
    )

    assert manifest["dataset_key"] == "daily_bars"
    assert manifest["row_count"] == 3
    assert manifest["quality"]["status"] == "fail"
    assert manifest["quality"]["backfill_task_id"] is not None
    assert manifest["files"]
    loaded = load_manifest(manifest["manifest_path"])
    assert loaded["dataset_version"] == manifest["dataset_version"]


def _bar(symbol: str, trade_date: date) -> DailyBarSnapshot:
    return DailyBarSnapshot(
        symbol=symbol,
        market="CN",
        instrument_type="stock",
        trade_date=trade_date,
        open_price=10,
        high_price=11,
        low_price=9,
        close_price=10.5,
        pre_close=10,
        volume=1000,
        amount=10000,
        pct_chg=5,
        source="test",
        fetch_time="2026-05-30T00:00:00",
        adjusted_mode="qfq",
        checksum="x",
        data_quality="fresh",
    )
