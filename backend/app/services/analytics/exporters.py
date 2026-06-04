from __future__ import annotations

import json
from datetime import date, datetime
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.services.analytics.config import analytics_config
from app.services.analytics.dependencies import require_analytics_dependencies
from app.services.analytics.manifest import dataset_version, file_sha256, write_manifest
from app.models.entities import DailyBarSnapshot
from app.services.analytics.quality import check_daily_bars_24m_quality, normalized_quality_status, period_for_months
from app.services.analytics.schemas import DAILY_BARS_SCHEMA


def export_daily_bars_parquet(
    db: Session,
    *,
    months: int = 24,
    end_date: date | None = None,
    output_root: str | Path | None = None,
    create_backfill_task: bool = True,
) -> dict[str, Any]:
    require_analytics_dependencies()
    config = analytics_config(output_root)
    config.ensure_dirs()
    resolved_end = end_date or date.today()
    period_start, period_end = period_for_months(resolved_end, months)
    quality = check_daily_bars_24m_quality(
        db,
        months=months,
        end_date=resolved_end,
        create_backfill_task=create_backfill_task,
    )
    generated_at = datetime.utcnow()
    source_updated_at = _latest_source_updated_at(db, period_start=period_start, period_end=period_end)
    version = dataset_version("daily_bars", generated_at)
    files: list[dict[str, Any]] = []
    row_count = 0
    if quality.row_count:
        for year, month in _months_between(period_start, period_end):
            month_start = date(year, month, 1)
            month_end = _month_end(month_start)
            start = max(month_start, period_start)
            end = min(month_end, period_end)
            frame = pd.read_sql_query(
                text(
                    """
                    SELECT
                        symbol,
                        trade_date,
                        open_price AS open,
                        high_price AS high,
                        low_price AS low,
                        close_price AS close,
                        pre_close,
                        volume,
                        amount,
                        pct_chg,
                        adjusted_mode AS adjusted,
                        source,
                        updated_at AS loaded_at,
                        data_quality
                    FROM daily_bar_snapshots
                    WHERE instrument_type = 'stock'
                        AND trade_date >= :start_date
                        AND trade_date <= :end_date
                    ORDER BY trade_date ASC, symbol ASC
                    """
                ),
                db.connection(),
                params={"start_date": start.isoformat(), "end_date": end.isoformat()},
            )
            if frame.empty:
                continue
            target_dir = config.parquet_dir / "daily_bars" / f"trade_year={year}" / f"trade_month={month:02d}"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / "part-000.parquet"
            frame.to_parquet(target, index=False, engine="pyarrow")
            rows = int(len(frame))
            row_count += rows
            files.append(
                {
                    "path": str(target.relative_to(config.root)),
                    "rows": rows,
                    "sha256": file_sha256(target),
                }
            )
    manifest = {
        "dataset": DAILY_BARS_SCHEMA.dataset_key,
        "dataset_key": DAILY_BARS_SCHEMA.dataset_key,
        "schema_version": DAILY_BARS_SCHEMA.schema_version,
        "dataset_version": version,
        "generated_at": generated_at.isoformat(timespec="seconds") + "Z",
        "status": normalized_quality_status(quality),
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "date_range": {
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
            "months": months,
            "requested_end_date": resolved_end.isoformat(),
        },
        "row_count": row_count,
        "symbol_count": quality.symbol_count,
        "coverage": {
            "expected_days": quality.expected_days,
            "actual_days": quality.actual_days,
            "missing_days": quality.missing_days,
            "complete_trade_day_count": quality.complete_trade_day_count,
            "coverage_pct": (
                round(float(quality.actual_days) / float(quality.expected_days) * 100.0, 4)
                if quality.expected_days
                else 0.0
            ),
            "complete_coverage_pct": (
                round(float(quality.complete_trade_day_count) / float(quality.expected_days) * 100.0, 4)
                if quality.expected_days
                else 0.0
            ),
        },
        "source": {
            "type": "transaction_db",
            "snapshot": generated_at.isoformat(timespec="seconds") + "Z",
            "latest_db_updated_at": source_updated_at,
            "source_table": "daily_bar_snapshots",
        },
        "quality": quality.as_dict(),
        "quality_status": normalized_quality_status(quality),
        "artifact_paths": [item["path"] for item in files],
        "files": files,
    }
    path = write_manifest(manifest, output_root=config.root)
    manifest["manifest_path"] = str(path)
    return manifest


def _months_between(start: date, end: date):
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        yield year, month
        month += 1
        if month > 12:
            year += 1
            month = 1


def _month_end(value: date) -> date:
    if value.month == 12:
        return date(value.year, 12, 31)
    return date(value.year, value.month + 1, 1) - timedelta(days=1)


def _latest_source_updated_at(db: Session, *, period_start: date, period_end: date) -> str:
    value = db.execute(
        select(func.max(DailyBarSnapshot.updated_at)).where(
            DailyBarSnapshot.instrument_type == "stock",
            DailyBarSnapshot.trade_date >= period_start,
            DailyBarSnapshot.trade_date <= period_end,
        )
    ).scalar()
    return value.isoformat(timespec="seconds") + "Z" if value else ""
