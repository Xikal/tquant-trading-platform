from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.analytics.config import analytics_config
from app.services.analytics.dependencies import require_analytics_dependencies
from app.services.analytics.manifest import dataset_version, file_sha256, write_manifest
from app.services.analytics.schemas import (
    BACKTEST_DAILY_SNAPSHOTS_SCHEMA,
    BACKTEST_RUNS_SCHEMA,
    BACKTEST_TRADES_SCHEMA,
    AnalyticsDatasetSchema,
)

_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def export_backtest_runs_parquet(
    db: Session,
    *,
    days: int = 180,
    end_date: date | None = None,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    return _export_backtest_dataset_parquet(
        db,
        schema=BACKTEST_RUNS_SCHEMA,
        source_table="backtest_runs",
        date_column="created_at",
        partition_name="created_date",
        columns_sql="""
            id,
            name,
            params_json,
            result_json,
            owner_user_id,
            status,
            strategy_keys,
            start_date,
            end_date,
            benchmark_symbol,
            initial_cash,
            final_equity,
            progress_pct,
            max_duration_seconds,
            optimization_id,
            validation_id,
            dataset_manifest_id,
            engine_version,
            strategy_version,
            data_version,
            fee_model_version,
            slippage_bps,
            error_message,
            started_at,
            finished_at,
            cancelled_at,
            deleted_at,
            created_at,
            updated_at
        """,
        order_by="created_at ASC, id ASC",
        source_updated_column="updated_at",
        no_data_blocker="backtest_runs_no_rows",
        days=days,
        end_date=end_date,
        output_root=output_root,
    )


def export_backtest_trades_parquet(
    db: Session,
    *,
    days: int = 180,
    end_date: date | None = None,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    return _export_backtest_dataset_parquet(
        db,
        schema=BACKTEST_TRADES_SCHEMA,
        source_table="backtest_trades",
        date_column="trade_date",
        partition_name="trade_date",
        columns_sql="""
            id,
            run_id,
            order_id,
            trade_date,
            symbol,
            name,
            side,
            strategy_key,
            signal_state,
            quantity,
            price,
            gross_amount,
            fee_amount,
            slippage_amount,
            net_amount,
            pnl_amount,
            pnl_pct,
            holding_days,
            entry_reason,
            exit_reason,
            market_state,
            sector,
            sector_name,
            payload_json,
            created_at
        """,
        order_by="trade_date ASC, run_id ASC, id ASC",
        source_updated_column="created_at",
        no_data_blocker="backtest_trades_no_rows",
        days=days,
        end_date=end_date,
        output_root=output_root,
    )


def export_backtest_daily_snapshots_parquet(
    db: Session,
    *,
    days: int = 180,
    end_date: date | None = None,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    return _export_backtest_dataset_parquet(
        db,
        schema=BACKTEST_DAILY_SNAPSHOTS_SCHEMA,
        source_table="backtest_daily_snapshots",
        date_column="trade_date",
        partition_name="trade_date",
        columns_sql="""
            id,
            run_id,
            trade_date,
            cash,
            market_value,
            equity,
            daily_return_pct,
            drawdown_pct,
            exposure_pct,
            positions_count,
            turnover,
            benchmark_symbol,
            benchmark_close,
            benchmark_return_pct,
            market_state,
            payload_json,
            created_at
        """,
        order_by="trade_date ASC, run_id ASC, id ASC",
        source_updated_column="created_at",
        no_data_blocker="backtest_daily_snapshots_no_rows",
        days=days,
        end_date=end_date,
        output_root=output_root,
    )


def _export_backtest_dataset_parquet(
    db: Session,
    *,
    schema: AnalyticsDatasetSchema,
    source_table: str,
    date_column: str,
    partition_name: str,
    columns_sql: str,
    order_by: str,
    source_updated_column: str,
    no_data_blocker: str,
    days: int,
    end_date: date | None,
    output_root: str | Path | None,
) -> dict[str, Any]:
    _validate_identifier(source_table)
    _validate_identifier(date_column)
    _validate_identifier(partition_name)
    _validate_identifier(source_updated_column)
    require_analytics_dependencies()
    config = analytics_config(output_root)
    config.ensure_dirs()
    resolved_end = end_date or date.today()
    window_days = max(int(days or 180), 1)
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
    source_updated_at = _latest_backtest_source_updated_at(
        db,
        source_table=source_table,
        date_column=date_column,
        updated_column=source_updated_column,
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
            "source_date_column": date_column,
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


def _latest_backtest_source_updated_at(
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


def _validate_identifier(value: str) -> None:
    if not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"invalid SQL identifier: {value}")
