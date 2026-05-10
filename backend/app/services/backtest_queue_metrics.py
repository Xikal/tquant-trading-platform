from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import BacktestRun
from app.services.low_buy.strategy_parameter_defaults import BACKTEST_EXECUTION_DEFAULTS
from app.services.quant.runtime_parameters import get_backtest_execution

_ESTIMATED_SECONDS_PER_RUN = 60


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
    return BacktestQueueSnapshot(
        queue_depth=queue_depth,
        queue_position=queue_position,
        running_count=running_count,
        estimated_wait_seconds=_estimated_wait_seconds(queue_position, running_count),
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


def _estimated_wait_seconds(queue_position: int | None, running_count: int) -> int:
    if not queue_position:
        return 0
    max_concurrent = _max_concurrent_backtests()
    free_slots = max(max_concurrent - running_count, 0)
    jobs_waiting_before_slot = max(queue_position - max(free_slots, 1), 0)
    batches_ahead = (jobs_waiting_before_slot + max_concurrent - 1) // max_concurrent
    return int(batches_ahead * _ESTIMATED_SECONDS_PER_RUN)


def _max_concurrent_backtests() -> int:
    try:
        params = get_backtest_execution()
        value = int(float(params.get("max_concurrent_backtests") or BACKTEST_EXECUTION_DEFAULTS["max_concurrent_backtests"]))
    except Exception:
        value = int(BACKTEST_EXECUTION_DEFAULTS["max_concurrent_backtests"])
    return max(1, min(value, 8))
