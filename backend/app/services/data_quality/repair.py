from __future__ import annotations

import json
import os
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.entities import DailyBarSnapshot, DataRepairAudit
from app.repositories.low_buy.daily_history import DailyBarRow, DailyHistoryRepository
from app.services.analytics.config import PROJECT_ROOT
from app.services.analytics.quality import daily_bar_invalid_ohlc_filter


InvalidRowsRefetcher = Callable[[list[dict[str, object]]], dict[tuple[str, str], list[DailyBarRow]]]


@dataclass(frozen=True)
class DataRepairResult:
    status: str
    dataset_key: str
    matched_rows: int
    deleted_rows: int = 0
    refetched_rows: int = 0
    backup_path: str = ""
    row_backup_path: str = ""
    repair_id: str = ""
    fabricated: bool = False
    refetch_result: str = ""
    audit_path: str = ""
    sample: list[dict[str, object]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "dataset_key": self.dataset_key,
            "matched_rows": self.matched_rows,
            "deleted_rows": self.deleted_rows,
            "refetched_rows": self.refetched_rows,
            "backup_path": self.backup_path,
            "row_backup_path": self.row_backup_path,
            "repair_id": self.repair_id,
            "fabricated": self.fabricated,
            "refetch_result": self.refetch_result,
            "audit_path": self.audit_path,
            "sample": self.sample,
        }


def repair_invalid_ohlc(
    db: Session,
    *,
    dataset_key: str,
    dry_run: bool,
    backup_dir: str | Path | None = None,
    output_path: str | Path | None = None,
    refetch: bool = True,
    refetcher: InvalidRowsRefetcher | None = None,
    operator: str = "system",
) -> DataRepairResult:
    if dataset_key != "daily_bars":
        raise ValueError(f"unsupported repair dataset: {dataset_key}")
    rows = _load_invalid_daily_bar_rows(db)
    if dry_run:
        result = DataRepairResult(
            status="dry_run",
            dataset_key=dataset_key,
            matched_rows=len(rows),
            sample=rows[:20],
        )
        _write_optional_output(output_path, result.as_dict())
        return result
    if not rows:
        result = DataRepairResult(status="completed", dataset_key=dataset_key, matched_rows=0)
        _write_optional_output(output_path, result.as_dict())
        return result
    repair_id = f"repair-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    resolved_backup_dir = _resolve_backup_dir(backup_dir)
    db_backup_path = _backup_database(db, resolved_backup_dir)
    row_backup_path = _write_row_backup(resolved_backup_dir, repair_id, rows)
    refetched_keys: set[tuple[str, str]] = set()
    refetch_status = "skipped"
    if refetch and rows:
        refetched = (refetcher or _default_refetcher)(rows)
        refetched_count = _upsert_refetched_rows(db, refetched)
        refetched_keys = set(refetched)
        refetch_status = f"updated:{refetched_count}" if refetched_count else "empty"
    else:
        refetched_count = 0

    deletable_rows = [
        row for row in rows
        if (str(row["symbol"]), str(row["trade_date"])) not in refetched_keys
    ]
    deleted_rows = _delete_rows(db, [int(row["id"]) for row in deletable_rows])
    audit = DataRepairAudit(
        repair_id=repair_id,
        dataset_key=dataset_key,
        reason="daily_bars_invalid_ohlc",
        detected_rows_json=json.dumps(rows, ensure_ascii=False, sort_keys=True),
        backup_path=str(db_backup_path),
        refetch_result=refetch_status,
        deleted_rows_json=json.dumps(deletable_rows, ensure_ascii=False, sort_keys=True),
        fabricated=False,
        operator=operator,
    )
    db.add(audit)
    db.commit()
    result = DataRepairResult(
        status="completed",
        dataset_key=dataset_key,
        matched_rows=len(rows),
        deleted_rows=deleted_rows,
        refetched_rows=refetched_count,
        backup_path=str(db_backup_path),
        row_backup_path=str(row_backup_path),
        repair_id=repair_id,
        fabricated=False,
        refetch_result=refetch_status,
        sample=rows[:20],
    )
    audit_path = _write_optional_output(output_path, result.as_dict())
    if audit_path:
        result = DataRepairResult(**{**result.as_dict(), "audit_path": audit_path})  # type: ignore[arg-type]
    return result


def _load_invalid_daily_bar_rows(db: Session) -> list[dict[str, object]]:
    rows = db.execute(
        select(
            DailyBarSnapshot.id,
            DailyBarSnapshot.symbol,
            DailyBarSnapshot.trade_date,
            DailyBarSnapshot.open_price,
            DailyBarSnapshot.close_price,
            DailyBarSnapshot.high_price,
            DailyBarSnapshot.low_price,
            DailyBarSnapshot.volume,
            DailyBarSnapshot.amount,
            DailyBarSnapshot.source,
            DailyBarSnapshot.data_quality,
        )
        .where(
            DailyBarSnapshot.instrument_type == "stock",
            daily_bar_invalid_ohlc_filter(),
        )
        .order_by(DailyBarSnapshot.trade_date.asc(), DailyBarSnapshot.symbol.asc())
    ).mappings().all()
    return [_json_safe_row(row) for row in rows]


def _backup_database(db: Session, backup_dir: Path) -> Path:
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "sqlite":
        return _backup_sqlite_session(db, backup_dir)
    script = PROJECT_ROOT / "scripts" / "backup_database.sh"
    if not script.exists():
        raise RuntimeError(f"database backup script missing: {script}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    before = _backup_files(backup_dir)
    completed = subprocess.run(
        [str(script)],
        cwd=PROJECT_ROOT,
        env={**os.environ, "BACKUP_DIR": str(backup_dir)},
        text=True,
        capture_output=True,
        timeout=600,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "database backup failed")[-1000:])
    after = _backup_files(backup_dir)
    created = sorted(after - before)
    if not created:
        raise RuntimeError("database backup did not create an artifact")
    return created[-1]


def _backup_sqlite_session(db: Session, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"t_quant-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}.sql"
    raw = db.connection().connection
    driver = getattr(raw, "driver_connection", raw)
    if hasattr(driver, "iterdump"):
        dump = "\n".join(driver.iterdump())
    else:
        dump = "-- sqlite backup unavailable for this driver\n"
    target.write_text(dump + "\n", encoding="utf-8")
    return target


def _backup_files(backup_dir: Path) -> set[Path]:
    return set(backup_dir.glob("t_quant-*.db.gz")) | set(backup_dir.glob("t_quant-*.sql.gz"))


def _write_row_backup(backup_dir: Path, repair_id: str, rows: list[dict[str, object]]) -> Path:
    path = backup_dir / f"{repair_id}-rows.json"
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _upsert_refetched_rows(db: Session, refetched: dict[tuple[str, str], list[DailyBarRow]]) -> int:
    total = 0
    for (symbol, _trade_date), rows in refetched.items():
        if not rows:
            continue
        DailyHistoryRepository(db).upsert_rows(symbol=symbol, payloads=rows)
        total += len(rows)
    if total:
        db.flush()
    return total


def _delete_rows(db: Session, row_ids: Iterable[int]) -> int:
    ids = list(row_ids)
    if not ids:
        return 0
    result = db.execute(delete(DailyBarSnapshot).where(DailyBarSnapshot.id.in_(ids)))
    return int(result.rowcount or 0)


def _write_optional_output(output_path: str | Path | None, payload: dict[str, object]) -> str:
    if not output_path:
        return ""
    path = Path(output_path).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)


def _default_refetcher(rows: list[dict[str, object]]) -> dict[tuple[str, str], list[DailyBarRow]]:
    # The full remote refetch path is exposed through backfill_daily_history.py.
    # This repair primitive refuses to fabricate replacement prices; empty means delete only after backup.
    return {}


def _resolve_backup_dir(value: str | Path | None) -> Path:
    raw = Path(value) if value else PROJECT_ROOT / "backups" / "data_quality"
    raw = raw.expanduser()
    return raw if raw.is_absolute() else PROJECT_ROOT / raw


def _json_safe_row(row) -> dict[str, object]:  # noqa: ANN001
    result: dict[str, object] = {}
    for key, value in dict(row).items():
        result[str(key)] = value.isoformat() if hasattr(value, "isoformat") else value
    return result
