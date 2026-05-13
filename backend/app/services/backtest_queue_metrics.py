from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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


def backtest_queue_snapshot(db: Session, row: BacktestRun) -> BacktestQueueSnapshot:
    queue_depth = _count_status(db, "queued")
    running_count = _count_status(db, "running")
    queue_position = _queue_position(db, row) if row.status == "queued" else None
    timeline = _timeline_rows(db)
    return BacktestQueueSnapshot(
        queue_depth=queue_depth,
        queue_position=queue_position,
        running_count=running_count,
        estimated_wait_seconds=_estimated_wait_seconds(row, timeline),
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


def _estimated_wait_seconds(row: BacktestRun, timeline: list[dict[str, Any]]) -> int:
    if row.status != "queued":
        return 0
    max_concurrent = _max_concurrent_backtests()
    if max_concurrent <= 1:
        return int(sum(item["cost_seconds"] for item in timeline if _ahead_of(item, row)))
    total_cost_before = sum(item["cost_seconds"] for item in timeline if _ahead_of(item, row))
    return int(total_cost_before / max_concurrent)


def _timeline_rows(db: Session) -> list[dict[str, Any]]:
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
        timeline.append(
            {
                "id": int(run_id),
                "status": str(status or "queued"),
                "created_at": created_at,
                "started_at": started_at,
                "cost_seconds": estimated_seconds_for_tier(tier),
            }
        )
    timeline.sort(key=lambda item: _timeline_sort_key(item))
    return timeline


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
