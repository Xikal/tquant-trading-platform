from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.analytics.manifest import load_manifest


@dataclass(frozen=True)
class RetentionPolicy:
    dataset_key: str
    source_table: str
    source_date_column: str
    hot_days: int
    min_manifest_statuses: tuple[str, ...] = ("active", "ok")


RETENTION_POLICIES: dict[str, RetentionPolicy] = {
    "daily_bars": RetentionPolicy("daily_bars", "daily_bar_snapshots", "trade_date", 730),
    "strategy_tracking_snapshots": RetentionPolicy(
        "strategy_tracking_snapshots",
        "strategy_tracking_snapshots",
        "generated_at",
        90,
    ),
    "key_level_snapshots": RetentionPolicy("key_level_snapshots", "key_level_snapshots", "trade_date", 90),
    "low_buy_result_snapshots": RetentionPolicy(
        "low_buy_result_snapshots",
        "low_buy_result_snapshots",
        "latest_trade_date",
        90,
    ),
    "backtest_runs": RetentionPolicy("backtest_runs", "backtest_runs", "created_at", 180),
    "backtest_trades": RetentionPolicy("backtest_trades", "backtest_trades", "trade_date", 180),
    "backtest_daily_snapshots": RetentionPolicy(
        "backtest_daily_snapshots",
        "backtest_daily_snapshots",
        "trade_date",
        180,
    ),
    "analysis_logs": RetentionPolicy("analysis_logs", "analysis_logs", "created_at", 90),
    "market_review_reports": RetentionPolicy("market_review_reports", "market_review_reports", "report_date", 90),
    "paper_review_reports": RetentionPolicy("paper_review_reports", "paper_review_reports", "report_date", 90),
}


def build_retention_plan(
    db: Session,
    *,
    manifest: str | Path | dict[str, Any],
    as_of_date: date | None = None,
    hot_days: int | None = None,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    """Build a read-only MySQL retention candidate plan from a Parquet manifest.

    The plan is intentionally non-destructive: it never deletes rows, never
    purges binlogs, and never mutates the manifest. Operators can use the
    returned evidence to decide whether a later, separately authorized cleanup
    is safe.
    """

    payload = dict(manifest) if isinstance(manifest, dict) else load_manifest(manifest, output_root=output_root)
    dataset_key = str(payload.get("dataset_key") or payload.get("dataset") or "")
    policy = RETENTION_POLICIES.get(dataset_key)
    if policy is None:
        return _blocked(payload, dataset_key=dataset_key, blockers=[f"retention_policy_missing:{dataset_key}"])

    resolved_hot_days = max(int(hot_days if hot_days is not None else policy.hot_days), 1)
    resolved_as_of = as_of_date or date.today()
    keep_after = resolved_as_of - timedelta(days=resolved_hot_days - 1)
    validation = _validate_manifest_for_retention(payload, policy=policy)
    candidate_row_count = 0
    candidate_range: dict[str, str] = {}
    if not validation["blockers"]:
        candidate_range = {
            "start": str(payload.get("period_start") or ""),
            "end": min(str(payload.get("period_end") or ""), keep_after.isoformat()),
        }
        if candidate_range["start"] and candidate_range["end"] and candidate_range["start"] <= candidate_range["end"]:
            candidate_row_count = _count_candidate_rows(
                db,
                table=policy.source_table,
                date_column=policy.source_date_column,
                start_date=candidate_range["start"],
                end_date=candidate_range["end"],
            )
        else:
            validation["blockers"].append("retention_window_no_cold_rows")

    ready = not validation["blockers"] and candidate_row_count > 0
    if candidate_row_count <= 0 and not validation["blockers"]:
        validation["blockers"].append("retention_candidate_rows_zero")
    return {
        "dataset_key": dataset_key,
        "manifest_id": payload.get("manifest_id"),
        "manifest_path": payload.get("manifest_path"),
        "source_table": policy.source_table,
        "source_date_column": policy.source_date_column,
        "as_of_date": resolved_as_of.isoformat(),
        "hot_days": resolved_hot_days,
        "keep_after": keep_after.isoformat(),
        "candidate_range": candidate_range,
        "candidate_row_count": candidate_row_count,
        "manifest_row_count": int(payload.get("row_count") or 0),
        "files": payload.get("files") or [],
        "checks": validation["checks"],
        "blockers": validation["blockers"],
        "ready_for_separate_cleanup_authorization": ready,
        "dry_run_sql": _dry_run_sql(policy.source_table, policy.source_date_column),
        "cleanup_sql_template": _cleanup_sql_template(policy.source_table, policy.source_date_column),
        "safety": {
            "read_only": True,
            "requires_separate_cleanup_authorization": True,
            "mysql_source_not_deleted_by_planner": True,
            "requires_backup_before_cleanup": True,
            "requires_restore_path": True,
        },
    }


def build_retention_plans(
    db: Session,
    *,
    manifests: list[str | Path | dict[str, Any]],
    as_of_date: date | None = None,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    plans = [
        build_retention_plan(db, manifest=manifest, as_of_date=as_of_date, output_root=output_root)
        for manifest in manifests
    ]
    return {
        "ok": all(plan["ready_for_separate_cleanup_authorization"] for plan in plans),
        "ready_count": sum(1 for plan in plans if plan["ready_for_separate_cleanup_authorization"]),
        "blocked_count": sum(1 for plan in plans if not plan["ready_for_separate_cleanup_authorization"]),
        "plans": plans,
    }


def _validate_manifest_for_retention(payload: dict[str, Any], *, policy: RetentionPolicy) -> dict[str, Any]:
    blockers: list[str] = []
    files = payload.get("files") or []
    status = str(payload.get("status") or "").lower()
    quality_status = str(payload.get("quality_status") or (payload.get("quality") or {}).get("status") or "").lower()
    row_count = int(payload.get("row_count") or 0)
    source = payload.get("source") or {}
    checks = {
        "dataset_key_matches": payload.get("dataset_key") == policy.dataset_key,
        "source_table_matches": source.get("source_table") == policy.source_table,
        "manifest_status": status,
        "quality_status": quality_status,
        "row_count": row_count,
        "files": len(files),
        "file_hashes_present": all(item.get("sha256") for item in files),
        "period_start": payload.get("period_start"),
        "period_end": payload.get("period_end"),
    }
    if checks["dataset_key_matches"] is False:
        blockers.append("manifest_dataset_mismatch")
    if checks["source_table_matches"] is False:
        blockers.append("manifest_source_table_mismatch")
    if status not in policy.min_manifest_statuses:
        blockers.append(f"manifest_status_not_active:{status or 'missing'}")
    if quality_status not in {"ok", "active"}:
        blockers.append(f"manifest_quality_not_ok:{quality_status or 'missing'}")
    if row_count <= 0:
        blockers.append("manifest_row_count_zero")
    if not files:
        blockers.append("manifest_files_missing")
    if files and not checks["file_hashes_present"]:
        blockers.append("manifest_file_hash_missing")
    if not payload.get("period_start") or not payload.get("period_end"):
        blockers.append("manifest_period_missing")
    return {"checks": checks, "blockers": blockers}


def _count_candidate_rows(db: Session, *, table: str, date_column: str, start_date: str, end_date: str) -> int:
    value = db.execute(
        text(
            f"""
            SELECT count(*)
            FROM {table}
            WHERE date({date_column}) >= :start_date
                AND date({date_column}) <= :end_date
            """
        ),
        {"start_date": start_date, "end_date": end_date},
    ).scalar()
    return int(value or 0)


def _dry_run_sql(table: str, date_column: str) -> str:
    return (
        f"SELECT count(*) FROM {table} "
        f"WHERE date({date_column}) >= :start_date AND date({date_column}) <= :end_date"
    )


def _cleanup_sql_template(table: str, date_column: str) -> str:
    return (
        "-- Not executed by retention planner. Requires backup, restore path, "
        "and separate operator authorization.\n"
        f"DELETE FROM {table} "
        f"WHERE date({date_column}) >= :start_date AND date({date_column}) <= :end_date"
    )


def _blocked(payload: dict[str, Any], *, dataset_key: str, blockers: list[str]) -> dict[str, Any]:
    return {
        "dataset_key": dataset_key,
        "manifest_id": payload.get("manifest_id"),
        "source_table": "",
        "source_date_column": "",
        "candidate_row_count": 0,
        "manifest_row_count": int(payload.get("row_count") or 0),
        "checks": {},
        "blockers": blockers,
        "ready_for_separate_cleanup_authorization": False,
        "dry_run_sql": "",
        "cleanup_sql_template": "",
        "safety": {
            "read_only": True,
            "requires_separate_cleanup_authorization": True,
            "mysql_source_not_deleted_by_planner": True,
        },
    }
