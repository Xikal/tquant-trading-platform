from __future__ import annotations

from datetime import datetime, time as dt_time
from typing import Any

from sqlalchemy.orm import Session

from app.core.timezone import beijing_now
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.repositories.low_buy import DailyHistoryRepository
from app.services.latest_data_status import (
    MIN_STOCK_DAILY_BARS,
    expected_low_buy_trade_date,
    latest_data_status,
    publish_latest_trade_date_if_ready,
)
from app.services.low_buy.strategy_policy import PRODUCTION_PRIORITY_STRATEGIES
from app.services.low_buy_materialization import enqueue_low_buy_materialization
from app.services.market.trading_calendar import is_a_share_trading_day
from app.services.tasks import RuntimeTaskQueue


CLOSE_REFRESH_AFTER = dt_time(hour=15, minute=1)
DAILY_BAR_REFRESH_TASK = "daily_bar_refresh"
STRATEGY_TRACKING_SNAPSHOT_TASK = "strategy_tracking_snapshot_refresh"


def enqueue_latest_data_close_refresh(
    db: Session,
    *,
    now: datetime | None = None,
    strategies: list[str] | None = None,
) -> dict[str, Any]:
    current = now or beijing_now()
    if current.time() < CLOSE_REFRESH_AFTER or not is_a_share_trading_day(current.date()):
        return {"ok": True, "action": "skip_before_close", "now": current.isoformat()}

    required = sorted(strategies or PRODUCTION_PRIORITY_STRATEGIES)
    expected = expected_low_buy_trade_date(db)
    daily_count = DailyHistoryRepository(db).stock_count_by_trade_date(expected) if expected else 0
    if not expected:
        return {"ok": False, "action": "missing_expected_trade_date"}

    if daily_count < MIN_STOCK_DAILY_BARS:
        task = RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
                task_type=DAILY_BAR_REFRESH_TASK,
                payload={"limit": 6000, "expected_trade_date": expected, "reason": "after_close_latest_data"},
                priority=20,
                idempotency_key=f"{DAILY_BAR_REFRESH_TASK}:{expected}",
                max_attempts=3,
            )
        )
        return {
            "ok": False,
            "action": "enqueue_daily_bar_refresh",
            "expected_trade_date": expected,
            "daily_bar_count": daily_count,
            "task_id": task.id,
            "task_status": task.status,
        }

    status = latest_data_status(db, strategies=required)
    missing = list(status.get("missing_strategies") or [])
    if status.get("published_trade_date") == expected and status.get("status") == "success":
        tracking_task = RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
                task_type=STRATEGY_TRACKING_SNAPSHOT_TASK,
                payload={"range_days": 30, "reason": "after_close_latest_data_already_latest"},
                priority=35,
                idempotency_key=f"{STRATEGY_TRACKING_SNAPSHOT_TASK}:{expected}:30",
                max_attempts=2,
            )
        )
        return {
            "ok": True,
            "action": "already_latest",
            "expected_trade_date": expected,
            "daily_bar_count": daily_count,
            "publish_status": status,
            "strategy_tracking_snapshot_task_id": tracking_task.id,
            "strategy_tracking_snapshot_task_status": tracking_task.status,
        }
    if missing:
        enqueue_low_buy_materialization(db, reason="after_close_latest_data", commit=True)
        return {
            "ok": False,
            "action": "enqueue_low_buy_materialization",
            "expected_trade_date": expected,
            "daily_bar_count": daily_count,
            "missing_strategies": missing,
        }

    publish_status = publish_latest_trade_date_if_ready(db, strategies=required)
    tracking_task = RuntimeTaskQueue(db).enqueue(
        RuntimeTaskCreate(
            task_type=STRATEGY_TRACKING_SNAPSHOT_TASK,
            payload={"range_days": 30, "reason": "after_close_latest_data"},
            priority=35,
            idempotency_key=f"{STRATEGY_TRACKING_SNAPSHOT_TASK}:{expected}:30",
            max_attempts=2,
        )
    )
    db.commit()
    return {
        "ok": publish_status.get("status") == "success",
        "action": "publish_latest_trade_date",
        "expected_trade_date": expected,
        "daily_bar_count": daily_count,
        "publish_status": publish_status,
        "strategy_tracking_snapshot_task_id": tracking_task.id,
        "strategy_tracking_snapshot_task_status": tracking_task.status,
    }
