from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import BacktestRun
from app.services.backtest.resource_tiers import estimated_seconds_for_tier, resource_tier_from_params_json
from app.services.low_buy.strategy_parameter_defaults import BACKTEST_EXECUTION_DEFAULTS
from app.services.quant.runtime_parameters import get_backtest_execution


@dataclass(frozen=True)
class BacktestQueueSnapshot:
    queue_depth: int
    queue_position: int | None
    running_count: int
    estimated_wait_seconds: int
    estimated_wait_reliable: bool
    estimated_wait_source: str


@dataclass(frozen=True)
class _EstimatedWait:
    seconds: int
    reliable: bool
    source: str


def backtest_queue_snapshot(db: Session, row: BacktestRun) -> BacktestQueueSnapshot:
    queue_depth = _count_status(db, "queued")
    running_count = _count_status(db, "running")
    queue_position = _queue_position(db, row) if row.status == "queued" else None
    timeline = _timeline_rows(db)
    estimate = _estimated_wait(row, timeline)
    return BacktestQueueSnapshot(
        queue_depth=queue_depth,
        queue_position=queue_position,
        running_count=running_count,
        estimated_wait_seconds=estimate.seconds,
        estimated_wait_reliable=estimate.reliable,
        estimated_wait_source=estimate.source,
    )


def _count_status(db: Session, status: str) -> int:
    return int(
        db.execute(
            select(func.count(BacktestRun.id)).where(
                BacktestRun.status == status,
                BacktestRun.deleted_at.is_(None),
            )
        ).scalar_one()
        or 0
    )


def _queue_position(db: Session, row: BacktestRun) -> int:
    return int(
        db.execute(
            select(func.count(BacktestRun.id)).where(
                BacktestRun.status == "queued",
                BacktestRun.deleted_at.is_(None),
                (BacktestRun.created_at < row.created_at)
                | ((BacktestRun.created_at == row.created_at) & (BacktestRun.id <= row.id)),
            )
        ).scalar_one()
        or 0
    )


def _estimated_wait(row: BacktestRun, timeline: list[dict[str, Any]]) -> _EstimatedWait:
    if row.status != "queued":
        return _EstimatedWait(seconds=0, reliable=True, source="not_queued")
    ahead = [item for item in timeline if _ahead_of(item, row)]
    if not ahead:
        return _EstimatedWait(seconds=0, reliable=True, source="no_wait")
    max_concurrent = _max_concurrent_backtests()
    reliable = all(bool(item.get("estimate_reliable")) for item in ahead)
    source = "historical_tier_average" if reliable else "fallback_resource_tier"
    if max_concurrent <= 1:
        return _EstimatedWait(seconds=int(sum(item["cost_seconds"] for item in ahead)), reliable=reliable, source=source)
    total_cost_before = sum(item["cost_seconds"] for item in ahead)
    return _EstimatedWait(seconds=int(total_cost_before / max_concurrent), reliable=reliable, source=source)


def _timeline_rows(db: Session) -> list[dict[str, Any]]:
    settings = _queue_estimate_settings()
    recent_seconds_by_tier = _recent_run_seconds_by_tier(
        db,
        per_tier_limit=settings["sample_size"],
        max_age_days=settings["max_age_days"],
    )
    rows = db.execute(
        select(
            BacktestRun.id,
            BacktestRun.status,
            BacktestRun.created_at,
            BacktestRun.started_at,
            BacktestRun.params_json,
        ).where(
            BacktestRun.status.in_(("queued", "running")),
            BacktestRun.deleted_at.is_(None),
        )
    ).all()
    timeline: list[dict[str, Any]] = []
    for run_id, status, created_at, started_at, params_json in rows:
        tier = resource_tier_from_params_json(params_json)
        has_history = tier in recent_seconds_by_tier
        timeline.append(
            {
                "id": int(run_id),
                "status": str(status or "queued"),
                "created_at": created_at,
                "started_at": started_at,
                "cost_seconds": int(recent_seconds_by_tier.get(tier) or estimated_seconds_for_tier(tier)),
                "estimate_reliable": has_history,
            }
        )
    timeline.sort(key=lambda item: _timeline_sort_key(item))
    return timeline


def _recent_run_seconds_by_tier(
    db: Session,
    *,
    per_tier_limit: int | None = None,
    max_age_days: int | None = None,
) -> dict[str, int]:
    settings = _queue_estimate_settings()
    limit = per_tier_limit if per_tier_limit is not None else settings["sample_size"]
    age_days = max_age_days if max_age_days is not None else settings["max_age_days"]
    query = (
        select(
            BacktestRun.params_json,
            BacktestRun.started_at,
            BacktestRun.finished_at,
        )
        .where(
            BacktestRun.status.in_(("succeeded", "failed", "cancelled", "timeout")),
            BacktestRun.deleted_at.is_(None),
            BacktestRun.started_at.is_not(None),
            BacktestRun.finished_at.is_not(None),
        )
    )
    if age_days > 0:
        query = query.where(BacktestRun.finished_at >= datetime.utcnow() - timedelta(days=age_days))
    rows = db.execute(
        query.order_by(BacktestRun.finished_at.desc(), BacktestRun.id.desc()).limit(limit * 8)
    ).all()
    grouped: dict[str, list[float]] = {}
    for params_json, started_at, finished_at in rows:
        if not isinstance(started_at, datetime) or not isinstance(finished_at, datetime):
            continue
        seconds = max((finished_at - started_at).total_seconds(), 1.0)
        tier = resource_tier_from_params_json(params_json)
        bucket = grouped.setdefault(tier, [])
        if len(bucket) < limit:
            bucket.append(seconds)
    return {tier: int(sum(values) / len(values)) for tier, values in grouped.items() if values}


def _ahead_of(item: dict[str, Any], row: BacktestRun) -> bool:
    item_status = str(item["status"])
    if item_status == "running":
        return True
    item_created = item.get("created_at")
    row_created = row.created_at
    if item_created is None or row_created is None:
        return int(item["id"]) < int(row.id)
    return (item_created, int(item["id"])) < (row_created, int(row.id))


def _timeline_sort_key(item: dict[str, Any]) -> tuple[int, datetime | None, datetime | None, int]:
    running_first = 0 if item["status"] == "running" else 1
    return (
        running_first,
        item.get("started_at"),
        item.get("created_at"),
        int(item["id"]),
    )


def _max_concurrent_backtests() -> int:
    try:
        params = get_backtest_execution()
        value = int(float(params.get("max_concurrent_backtests") or BACKTEST_EXECUTION_DEFAULTS["max_concurrent_backtests"]))
    except Exception:
        value = int(BACKTEST_EXECUTION_DEFAULTS["max_concurrent_backtests"])
    return max(1, min(value, 8))


def _queue_estimate_settings() -> dict[str, int]:
    try:
        params = get_backtest_execution()
    except Exception:
        params = {}
    sample_size = _int_param(
        params,
        "queue_estimate_sample_size",
        BACKTEST_EXECUTION_DEFAULTS["queue_estimate_sample_size"],
    )
    max_age_days = _int_param(
        params,
        "queue_estimate_max_age_days",
        BACKTEST_EXECUTION_DEFAULTS["queue_estimate_max_age_days"],
    )
    return {
        "sample_size": max(1, min(sample_size, 200)),
        "max_age_days": max(0, min(max_age_days, 3650)),
    }


def _int_param(params: dict[str, Any], key: str, default: Any) -> int:
    try:
        return int(float(params.get(key, default)))
    except (TypeError, ValueError):
        return int(default)
