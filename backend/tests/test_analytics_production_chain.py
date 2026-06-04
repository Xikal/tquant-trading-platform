from __future__ import annotations

import json
from datetime import date, timedelta
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import DailyBarSnapshot, RuntimeTask
from app.runtime import background_jobs
from app.services.analytics.exporters import export_daily_bars_parquet
from app.services.analytics.manifest import load_manifest
from app.services.analytics.quality import check_daily_bars_24m_quality


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def test_analytics_manifest_includes_operational_metadata_and_blocked_status(tmp_path) -> None:
    db = _db()
    for offset in range(3):
        db.add(_bar("000001", date(2026, 5, 27) + timedelta(days=offset)))
    db.commit()

    manifest = export_daily_bars_parquet(
        db,
        months=24,
        end_date=date(2026, 6, 4),
        output_root=tmp_path,
        create_backfill_task=True,
    )

    assert manifest["dataset"] == "daily_bars"
    assert manifest["date_range"]["months"] == 24
    assert manifest["coverage"]["actual_days"] == 3
    assert manifest["coverage"]["missing_days"] > 0
    assert manifest["source"]["source_table"] == "daily_bar_snapshots"
    assert manifest["quality_status"] in {"partial", "stale", "blocked", "no_data"}
    assert manifest["quality"]["backfill_task_id"] is not None
    assert manifest["artifact_paths"]
    loaded = load_manifest(manifest["manifest_path"])
    assert loaded["quality_status"] == manifest["quality_status"]
    assert loaded["manifest_path"] == manifest["manifest_path"]


def test_quality_no_data_uses_explicit_no_data_status_and_backfill_task() -> None:
    db = _db()

    quality = check_daily_bars_24m_quality(
        db,
        months=24,
        end_date=date(2026, 6, 4),
        create_backfill_task=True,
    )

    assert quality.as_dict()["canonical_status"] == "no_data"
    assert quality.backfill_task_id is not None
    task = db.get(RuntimeTask, quality.backfill_task_id)
    assert task is not None
    assert task.task_type == "data_backfill_24m"


def test_scheduler_enqueues_analytics_report_without_running_web_loop(monkeypatch) -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    monkeypatch.setattr(background_jobs, "SessionLocal", factory)
    monkeypatch.setattr(
        background_jobs,
        "settings",
        SimpleNamespace(analytics_24m_report_schedule_enabled=True),
    )
    monkeypatch.setattr(background_jobs, "beijing_now", lambda: date(2026, 6, 4))

    background_jobs._enqueue_analytics_24m_report_once()

    with factory() as db:
        tasks = db.execute(select(RuntimeTask)).scalars().all()
    assert len(tasks) == 1
    assert tasks[0].task_type == "strategy_24m_duckdb_report"
    assert json.loads(tasks[0].payload_json)["source"] == "scheduler"


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
        fetch_time="2026-06-04T00:00:00",
        adjusted_mode="qfq",
        checksum="x",
        data_quality="fresh",
    )
