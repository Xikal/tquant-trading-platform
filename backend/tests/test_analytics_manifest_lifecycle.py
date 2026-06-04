from __future__ import annotations

import json
from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import DailyBarSnapshot
from app.services.analytics.exporters import export_daily_bars_parquet
from app.services.analytics.manifest import load_manifest, write_manifest


def test_daily_bars_manifest_has_lifecycle_fields(tmp_path) -> None:
    db = _db()
    db.add(_bar("000001", date(2026, 5, 29)))
    db.commit()

    manifest = export_daily_bars_parquet(
        db,
        months=1,
        end_date=date(2026, 5, 30),
        output_root=tmp_path,
        create_backfill_task=False,
    )

    loaded = load_manifest(manifest["manifest_path"])
    assert loaded["manifest_id"].startswith("daily_bars:")
    assert loaded["dataset_version"] == manifest["dataset_version"]
    assert loaded["generated_at"]
    assert loaded["valid_until"]
    assert loaded["superseded_by"] is None
    assert loaded["status"] in {"active", "stale", "partial", "blocked", "no_data"}


def test_new_manifest_marks_previous_version_stale_without_deleting(tmp_path) -> None:
    first_path = write_manifest(
        {
            "dataset_key": "daily_bars",
            "dataset_version": "daily_bars_20260604090000",
            "generated_at": "2026-06-04T09:00:00Z",
            "status": "active",
        },
        output_root=tmp_path,
    )
    second_path = write_manifest(
        {
            "dataset_key": "daily_bars",
            "dataset_version": "daily_bars_20260604100000",
            "generated_at": "2026-06-04T10:00:00Z",
            "status": "active",
        },
        output_root=tmp_path,
    )

    first = json.loads(first_path.read_text(encoding="utf-8"))
    second = json.loads(second_path.read_text(encoding="utf-8"))

    assert first_path.exists()
    assert second_path.exists()
    assert first["status"] == "stale"
    assert first["superseded_by"] == second["manifest_id"]
    assert second["status"] == "active"
    assert second["superseded_by"] is None


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


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
        fetch_time=(trade_date + timedelta(days=1)).isoformat(),
        adjusted_mode="qfq",
        checksum="x",
        data_quality="fresh",
    )
