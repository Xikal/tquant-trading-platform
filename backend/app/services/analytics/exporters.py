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
from app.models.entities import DailyBarSnapshot, StrategyTrackingSnapshot
from app.services.analytics.quality import check_daily_bars_24m_quality, normalized_quality_status, period_for_months
from app.services.analytics.schemas import (
    DAILY_BARS_SCHEMA,
    ANALYSIS_LOGS_SCHEMA,
    KEY_LEVEL_SNAPSHOTS_SCHEMA,
    LOW_BUY_RESULT_SNAPSHOTS_SCHEMA,
    MARKET_REVIEW_REPORTS_SCHEMA,
    PAPER_REVIEW_REPORTS_SCHEMA,
    STRATEGY_TRACKING_SNAPSHOTS_SCHEMA,
    AnalyticsDatasetSchema,
)


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
    quality_payload = quality.as_dict()
    manifest = {
        "dataset": DAILY_BARS_SCHEMA.dataset_key,
        "dataset_key": DAILY_BARS_SCHEMA.dataset_key,
        "schema_version": DAILY_BARS_SCHEMA.schema_version,
        "dataset_version": version,
        "manifest_id": f"{DAILY_BARS_SCHEMA.dataset_key}:{version}",
        "generated_at": generated_at.isoformat(timespec="seconds") + "Z",
        "status": normalized_quality_status(quality),
        "valid_until": (generated_at + timedelta(days=7)).isoformat(timespec="seconds") + "Z",
        "superseded_by": None,
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
            "required_trade_days": quality_payload["required_trade_days"],
            "actual_trade_days": quality_payload["actual_trade_days"],
            "complete_trade_days": quality_payload["complete_trade_days"],
            "missing_trade_days": quality_payload["missing_trade_days"],
            "over_coverage_trade_days": quality_payload["over_coverage_trade_days"],
            "coverage_status": quality_payload["coverage_status"],
            "required_start": quality_payload["required_start"],
            "required_end": quality_payload["required_end"],
            "actual_start": quality_payload["actual_start"],
            "actual_end": quality_payload["actual_end"],
            "expected_days": quality.expected_days,
            "actual_days": quality.actual_days,
            "missing_days": quality.missing_days,
            "complete_trade_day_count": quality.complete_trade_day_count,
            "coverage_pct": quality_payload["coverage_pct"],
            "complete_coverage_pct": quality_payload["complete_coverage_pct"],
        },
        "source": {
            "type": "transaction_db",
            "snapshot": generated_at.isoformat(timespec="seconds") + "Z",
            "latest_db_updated_at": source_updated_at,
            "source_table": "daily_bar_snapshots",
        },
        "quality": quality_payload,
        "quality_status": normalized_quality_status(quality),
        "artifact_paths": [item["path"] for item in files],
        "files": files,
    }
    path = write_manifest(manifest, output_root=config.root)
    manifest["manifest_path"] = str(path)
    return manifest


def export_strategy_tracking_snapshots_parquet(
    db: Session,
    *,
    days: int = 90,
    end_date: date | None = None,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    """Archive strategy tracking snapshots to Parquet for analysis-only reads.

    The exporter is intentionally read-only against MySQL. It creates a manifest
    and Parquet files but does not delete or mutate the online source table.
    """

    require_analytics_dependencies()
    config = analytics_config(output_root)
    config.ensure_dirs()
    resolved_end = end_date or date.today()
    window_days = max(int(days or 90), 1)
    period_start = resolved_end - timedelta(days=window_days - 1)
    period_end = resolved_end
    generated_at = datetime.utcnow()
    version = dataset_version(STRATEGY_TRACKING_SNAPSHOTS_SCHEMA.dataset_key, generated_at)
    source_updated_at = _latest_strategy_tracking_updated_at(db, period_start=period_start, period_end=period_end)
    frame = pd.read_sql_query(
        text(
            """
            SELECT
                id,
                snapshot_key,
                as_of_date,
                range_days,
                strategy_key,
                strategy_family,
                market_scope,
                filter_hash,
                data_version,
                status,
                generated_at,
                source_data_cutoff,
                payload_json,
                metrics_json,
                error_message,
                created_at,
                updated_at
            FROM strategy_tracking_snapshots
            WHERE date(generated_at) >= :start_date
                AND date(generated_at) <= :end_date
            ORDER BY generated_at ASC, id ASC
            """
        ),
        db.connection(),
        params={"start_date": period_start.isoformat(), "end_date": period_end.isoformat()},
    )
    files: list[dict[str, Any]] = []
    row_count = int(len(frame))
    if not frame.empty:
        for day, day_frame in frame.groupby(frame["generated_at"].map(lambda value: str(value)[:10]), sort=True):
            target_dir = config.parquet_dir / STRATEGY_TRACKING_SNAPSHOTS_SCHEMA.dataset_key / f"generated_date={day}"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / "part-000.parquet"
            day_frame.to_parquet(target, index=False, engine="pyarrow")
            files.append(
                {
                    "path": str(target.relative_to(config.root)),
                    "rows": int(len(day_frame)),
                    "sha256": file_sha256(target),
                }
            )
    quality_status = "ok" if row_count > 0 else "no_data"
    manifest = {
        "dataset": STRATEGY_TRACKING_SNAPSHOTS_SCHEMA.dataset_key,
        "dataset_key": STRATEGY_TRACKING_SNAPSHOTS_SCHEMA.dataset_key,
        "schema_version": STRATEGY_TRACKING_SNAPSHOTS_SCHEMA.schema_version,
        "dataset_version": version,
        "manifest_id": f"{STRATEGY_TRACKING_SNAPSHOTS_SCHEMA.dataset_key}:{version}",
        "generated_at": generated_at.isoformat(timespec="seconds") + "Z",
        "status": quality_status,
        "quality_status": quality_status,
        "valid_until": (generated_at + timedelta(days=7)).isoformat(timespec="seconds") + "Z",
        "superseded_by": None,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "date_range": {
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
            "days": window_days,
            "requested_end_date": resolved_end.isoformat(),
        },
        "row_count": row_count,
        "source": {
            "type": "transaction_db",
            "snapshot": generated_at.isoformat(timespec="seconds") + "Z",
            "latest_db_updated_at": source_updated_at,
            "source_table": "strategy_tracking_snapshots",
        },
        "quality": {
            "status": quality_status,
            "row_count": row_count,
            "blockers": [] if row_count else ["strategy_tracking_snapshots_no_rows"],
        },
        "artifact_paths": [item["path"] for item in files],
        "files": files,
    }
    path = write_manifest(manifest, output_root=config.root)
    manifest["manifest_path"] = str(path)
    return manifest


def export_key_level_snapshots_parquet(
    db: Session,
    *,
    days: int = 90,
    end_date: date | None = None,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    return _export_simple_snapshot_dataset_parquet(
        db,
        schema=KEY_LEVEL_SNAPSHOTS_SCHEMA,
        source_table="key_level_snapshots",
        date_column="trade_date",
        partition_name="trade_date",
        columns_sql="""
            id,
            scope,
            cache_key,
            symbol,
            trade_date,
            engine_version,
            data_quality,
            payload_json,
            created_at,
            updated_at
        """,
        order_by="trade_date ASC, id ASC",
        no_data_blocker="key_level_snapshots_no_rows",
        days=days,
        end_date=end_date,
        output_root=output_root,
    )


def export_low_buy_result_snapshots_parquet(
    db: Session,
    *,
    days: int = 90,
    end_date: date | None = None,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    return _export_simple_snapshot_dataset_parquet(
        db,
        schema=LOW_BUY_RESULT_SNAPSHOTS_SCHEMA,
        source_table="low_buy_result_snapshots",
        date_column="latest_trade_date",
        partition_name="latest_trade_date",
        columns_sql="""
            id,
            latest_trade_date,
            strategy_key,
            symbol,
            name,
            score,
            buy_signal_state,
            payload_json,
            created_at,
            updated_at
        """,
        order_by="latest_trade_date ASC, strategy_key ASC, symbol ASC",
        no_data_blocker="low_buy_result_snapshots_no_rows",
        days=days,
        end_date=end_date,
        output_root=output_root,
    )


def export_analysis_logs_parquet(
    db: Session,
    *,
    days: int = 90,
    end_date: date | None = None,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    return _export_simple_snapshot_dataset_parquet(
        db,
        schema=ANALYSIS_LOGS_SCHEMA,
        source_table="analysis_logs",
        date_column="created_at",
        partition_name="created_date",
        columns_sql="""
            id,
            symbol,
            action,
            signal_score,
            risk_level,
            payload_json,
            created_at
        """,
        order_by="created_at ASC, id ASC",
        no_data_blocker="analysis_logs_no_rows",
        days=days,
        end_date=end_date,
        output_root=output_root,
        updated_column="created_at",
    )


def export_market_review_reports_parquet(
    db: Session,
    *,
    days: int = 90,
    end_date: date | None = None,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    return _export_simple_snapshot_dataset_parquet(
        db,
        schema=MARKET_REVIEW_REPORTS_SCHEMA,
        source_table="market_review_reports",
        date_column="report_date",
        partition_name="report_date",
        columns_sql="""
            id,
            report_date,
            report_slot,
            overall_summary,
            strategy_highlights,
            risk_alerts,
            suggestion,
            raw_metrics_snapshot,
            generated_at,
            llm_model
        """,
        order_by="report_date ASC, report_slot ASC, id ASC",
        no_data_blocker="market_review_reports_no_rows",
        days=days,
        end_date=end_date,
        output_root=output_root,
        updated_column="generated_at",
    )


def export_paper_review_reports_parquet(
    db: Session,
    *,
    days: int = 90,
    end_date: date | None = None,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    return _export_simple_snapshot_dataset_parquet(
        db,
        schema=PAPER_REVIEW_REPORTS_SCHEMA,
        source_table="paper_review_reports",
        date_column="report_date",
        partition_name="report_date",
        columns_sql="""
            id,
            account_id,
            report_date,
            report_slot,
            overall_summary,
            strategy_highlights,
            risk_alerts,
            suggestion,
            raw_metrics_snapshot,
            generated_at,
            llm_model
        """,
        order_by="report_date ASC, account_id ASC, report_slot ASC, id ASC",
        no_data_blocker="paper_review_reports_no_rows",
        days=days,
        end_date=end_date,
        output_root=output_root,
        updated_column="generated_at",
    )


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


def _latest_strategy_tracking_updated_at(db: Session, *, period_start: date, period_end: date) -> str:
    value = db.execute(
        select(func.max(StrategyTrackingSnapshot.updated_at)).where(
            func.date(StrategyTrackingSnapshot.generated_at) >= period_start.isoformat(),
            func.date(StrategyTrackingSnapshot.generated_at) <= period_end.isoformat(),
        )
    ).scalar()
    return value.isoformat(timespec="seconds") + "Z" if value else ""


def _export_simple_snapshot_dataset_parquet(
    db: Session,
    *,
    schema: AnalyticsDatasetSchema,
    source_table: str,
    date_column: str,
    partition_name: str,
    columns_sql: str,
    order_by: str,
    no_data_blocker: str,
    days: int,
    end_date: date | None,
    output_root: str | Path | None,
    updated_column: str = "updated_at",
) -> dict[str, Any]:
    require_analytics_dependencies()
    config = analytics_config(output_root)
    config.ensure_dirs()
    resolved_end = end_date or date.today()
    window_days = max(int(days or 90), 1)
    period_start = resolved_end - timedelta(days=window_days - 1)
    period_end = resolved_end
    generated_at = datetime.utcnow()
    version = dataset_version(schema.dataset_key, generated_at)
    frame = pd.read_sql_query(
        text(
            f"""
            SELECT
                {columns_sql}
            FROM {source_table}
            WHERE date({date_column}) >= :start_date
                AND date({date_column}) <= :end_date
            ORDER BY {order_by}
            """
        ),
        db.connection(),
        params={"start_date": period_start.isoformat(), "end_date": period_end.isoformat()},
    )
    files: list[dict[str, Any]] = []
    row_count = int(len(frame))
    if not frame.empty:
        for day, day_frame in frame.groupby(frame[date_column].map(lambda value: str(value)[:10]), sort=True):
            target_dir = config.parquet_dir / schema.dataset_key / f"{partition_name}={day}"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / "part-000.parquet"
            day_frame.to_parquet(target, index=False, engine="pyarrow")
            files.append(
                {
                    "path": str(target.relative_to(config.root)),
                    "rows": int(len(day_frame)),
                    "sha256": file_sha256(target),
                }
            )
    source_updated_at = _latest_simple_snapshot_updated_at(
        db,
        source_table=source_table,
        date_column=date_column,
        updated_column=updated_column,
        period_start=period_start,
        period_end=period_end,
    )
    quality_status = "ok" if row_count > 0 else "no_data"
    manifest = {
        "dataset": schema.dataset_key,
        "dataset_key": schema.dataset_key,
        "schema_version": schema.schema_version,
        "dataset_version": version,
        "manifest_id": f"{schema.dataset_key}:{version}",
        "generated_at": generated_at.isoformat(timespec="seconds") + "Z",
        "status": quality_status,
        "quality_status": quality_status,
        "valid_until": (generated_at + timedelta(days=7)).isoformat(timespec="seconds") + "Z",
        "superseded_by": None,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "date_range": {
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
            "days": window_days,
            "requested_end_date": resolved_end.isoformat(),
        },
        "row_count": row_count,
        "source": {
            "type": "transaction_db",
            "snapshot": generated_at.isoformat(timespec="seconds") + "Z",
            "latest_db_updated_at": source_updated_at,
            "source_table": source_table,
        },
        "quality": {
            "status": quality_status,
            "row_count": row_count,
            "blockers": [] if row_count else [no_data_blocker],
        },
        "artifact_paths": [item["path"] for item in files],
        "files": files,
    }
    path = write_manifest(manifest, output_root=config.root)
    manifest["manifest_path"] = str(path)
    return manifest


def _latest_simple_snapshot_updated_at(
    db: Session,
    *,
    source_table: str,
    date_column: str,
    updated_column: str,
    period_start: date,
    period_end: date,
) -> str:
    value = db.execute(
        text(
            f"""
            SELECT max({updated_column})
            FROM {source_table}
            WHERE date({date_column}) >= :start_date
                AND date({date_column}) <= :end_date
            """
        ),
        {"start_date": period_start.isoformat(), "end_date": period_end.isoformat()},
    ).scalar()
    return value.isoformat(timespec="seconds") + "Z" if hasattr(value, "isoformat") else str(value or "")
