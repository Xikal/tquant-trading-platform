from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import DailyBarSnapshot, DataRepairAudit
from app.repositories.low_buy.daily_history import DailyBarRow
from app.services.data_quality.repair import repair_invalid_ohlc


def test_repair_invalid_ohlc_dry_run_does_not_modify_rows(tmp_path: Path) -> None:
    db = _session()
    try:
        _add_invalid_rows(db, count=2)

        result = repair_invalid_ohlc(
            db,
            dataset_key="daily_bars",
            dry_run=True,
            backup_dir=tmp_path,
            refetcher=lambda rows: {},
        )

        assert result.status == "dry_run"
        assert result.matched_rows == 2
        assert result.deleted_rows == 0
        assert db.query(DailyBarSnapshot).count() == 2
        assert db.query(DataRepairAudit).count() == 0
    finally:
        db.close()


def test_repair_invalid_ohlc_apply_deletes_only_after_backup_and_is_idempotent(tmp_path: Path) -> None:
    db = _session()
    try:
        _add_invalid_rows(db, count=3)

        first = repair_invalid_ohlc(
            db,
            dataset_key="daily_bars",
            dry_run=False,
            backup_dir=tmp_path,
            refetcher=lambda rows: {},
            operator="pytest",
        )
        second = repair_invalid_ohlc(
            db,
            dataset_key="daily_bars",
            dry_run=False,
            backup_dir=tmp_path,
            refetcher=lambda rows: {},
            operator="pytest",
        )

        assert first.status == "completed"
        assert first.matched_rows == 3
        assert first.deleted_rows == 3
        assert first.fabricated is False
        assert first.backup_path
        assert Path(first.backup_path).exists()
        assert Path(first.row_backup_path).exists()
        assert db.query(DailyBarSnapshot).count() == 0
        audit = db.execute(select(DataRepairAudit)).scalar_one()
        assert audit.fabricated is False
        assert json.loads(audit.deleted_rows_json)
        assert second.matched_rows == 0
        assert second.deleted_rows == 0
    finally:
        db.close()


def test_repair_invalid_ohlc_refetch_success_updates_without_delete(tmp_path: Path) -> None:
    db = _session()
    try:
        _add_invalid_rows(db, count=1)

        result = repair_invalid_ohlc(
            db,
            dataset_key="daily_bars",
            dry_run=False,
            backup_dir=tmp_path,
            refetcher=lambda rows: {
                ("000001", "2026-05-25"): [
                    DailyBarRow(
                        trade_date="2026-05-25",
                        open_price=10.0,
                        high_price=10.5,
                        low_price=9.8,
                        close_price=10.2,
                        volume=1000,
                        amount=10000,
                        pct_chg=1.0,
                        source="refetch-test",
                        data_quality="verified",
                    )
                ]
            },
            operator="pytest",
        )

        row = db.execute(select(DailyBarSnapshot)).scalar_one()
        assert result.deleted_rows == 0
        assert result.refetched_rows == 1
        assert row.open_price == 10.0
        assert row.data_quality == "verified"
        audit = db.execute(select(DataRepairAudit)).scalar_one()
        assert json.loads(audit.deleted_rows_json) == []
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


def _add_invalid_rows(db, *, count: int) -> None:  # noqa: ANN001
    for index in range(count):
        db.add(
            DailyBarSnapshot(
                symbol=f"00000{index + 1}",
                market="CN",
                instrument_type="stock",
                trade_date=date(2026, 5, 25),
                open_price=0.0,
                close_price=10.0,
                high_price=10.5,
                low_price=9.8,
                volume=1000,
                amount=10000,
                source="unit-test",
                data_quality="invalid_ohlc",
            )
        )
    db.commit()
