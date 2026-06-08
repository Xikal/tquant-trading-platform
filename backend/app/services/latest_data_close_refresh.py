from __future__ import annotations

from datetime import date, datetime, time as dt_time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_now
from app.models.entities import DataQualitySnapshot, MarketReviewReport, PaperReviewReport, RuntimeTask
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.latest_data_status import (
    MIN_STOCK_DAILY_BARS,
    daily_bar_freshness_status,
    expected_low_buy_trade_date,
    latest_data_status,
    publish_latest_trade_date_if_ready,
)
from app.services.low_buy.strategy_policy import PRODUCTION_PRIORITY_STRATEGIES
from app.services.low_buy_materialization import TASK_TYPE as LOW_BUY_MATERIALIZATION_TASK
from app.services.low_buy_materialization import enqueue_low_buy_materialization
from app.services.market.trading_calendar import is_a_share_trading_day
from app.services.tasks import RuntimeTaskQueue


CLOSE_REFRESH_AFTER = dt_time(hour=15, minute=1)
MIDDAY_REVIEW_AFTER = dt_time(hour=11, minute=35)
MIDDAY_REVIEW_BEFORE = dt_time(hour=15, minute=0)
DEFAULT_CLOSE_REVIEW_AFTER = dt_time(hour=15, minute=5)
DAILY_BAR_REFRESH_TASK = "daily_bar_refresh"
STRATEGY_TRACKING_SNAPSHOT_TASK = "strategy_tracking_snapshot_refresh"
A_KEY_LEVEL_MATERIALIZATION_TASK = "a_key_level_materialization_refresh"
MARKET_REVIEW_TASK = "market_review_report"
PAPER_REVIEW_TASK = "paper_review_report"
DATA_QUALITY_SLA_TASK = "data_quality_sla_refresh"


def enqueue_latest_data_close_refresh(
    db: Session,
    *,
    now: datetime | None = None,
    strategies: list[str] | None = None,
) -> dict[str, Any]:
    current = now or beijing_now()
    if not is_a_share_trading_day(current.date()):
        return {
            "ok": True,
            "action": "skip_non_trading_day",
            "metric": "latest_data_close_refresh.skip_non_trading_day",
            "now": current.isoformat(),
        }
    if current.time() < CLOSE_REFRESH_AFTER:
        return {
            "ok": True,
            "action": "skip_before_close",
            "metric": "latest_data_close_refresh.skip_before_close",
            "now": current.isoformat(),
        }

    required = sorted(strategies or PRODUCTION_PRIORITY_STRATEGIES)
    expected = expected_low_buy_trade_date(db)
    if not expected:
        return {"ok": False, "action": "missing_expected_trade_date"}
    freshness = daily_bar_freshness_status(db, expected)
    daily_count = int(freshness.get("daily_bar_count") or 0)
    post_close_count = int(freshness.get("post_close_daily_bar_count") or 0)

    if daily_count < MIN_STOCK_DAILY_BARS or post_close_count < MIN_STOCK_DAILY_BARS:
        refresh_reason = (
            "after_close_stale_fetch_time"
            if daily_count >= MIN_STOCK_DAILY_BARS
            else "after_close_latest_data"
        )
        task = RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
                task_type=DAILY_BAR_REFRESH_TASK,
                payload={"limit": 6000, "expected_trade_date": expected, "reason": refresh_reason},
                priority=20,
                idempotency_key=f"{DAILY_BAR_REFRESH_TASK}:{expected}:{refresh_reason}",
                max_attempts=3,
            )
        )
        return {
            "ok": False,
            "action": "enqueue_daily_bar_refresh",
            "metric": "latest_data_close_refresh.enqueue_daily_bar_refresh",
            "expected_trade_date": expected,
            "daily_bar_count": daily_count,
            "post_close_daily_bar_count": post_close_count,
            "min_daily_bar_count": MIN_STOCK_DAILY_BARS,
            "daily_bar_freshness_status": freshness.get("daily_bar_freshness_status"),
            "post_close_fetch_cutoff": freshness.get("post_close_fetch_cutoff"),
            "latest_daily_bar_fetch_time": freshness.get("latest_daily_bar_fetch_time"),
            "task_id": task.id,
            "task_status": task.status,
        }

    key_level_task = _enqueue_a_key_level_materialization(
        db,
        trade_date=expected,
        reason="after_close_latest_data",
    )
    followups = enqueue_after_close_followups(
        db,
        trade_date=expected,
        now=current,
        strategies=required,
        reason="after_close_latest_data",
    )
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
            "metric": "latest_data_close_refresh.already_latest",
            "expected_trade_date": expected,
            "daily_bar_count": daily_count,
            "publish_status": status,
            "strategy_tracking_snapshot_task_id": tracking_task.id,
            "strategy_tracking_snapshot_task_status": tracking_task.status,
            "a_key_level_materialization_task_id": key_level_task.id,
            "a_key_level_materialization_task_status": key_level_task.status,
            "followups": followups,
        }
    if missing:
        enqueue_low_buy_materialization(db, reason="after_close_latest_data", commit=True)
        return {
            "ok": False,
            "action": "enqueue_low_buy_materialization",
            "metric": "latest_data_close_refresh.missing_strategy_snapshots",
            "expected_trade_date": expected,
            "daily_bar_count": daily_count,
            "missing_strategies": missing,
            "a_key_level_materialization_task_id": key_level_task.id,
            "a_key_level_materialization_task_status": key_level_task.status,
            "followups": followups,
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
        "metric": "latest_data_close_refresh.published_success"
        if publish_status.get("status") == "success"
        else "latest_data_close_refresh.publish_pending",
        "expected_trade_date": expected,
        "daily_bar_count": daily_count,
        "publish_status": publish_status,
        "strategy_tracking_snapshot_task_id": tracking_task.id,
        "strategy_tracking_snapshot_task_status": tracking_task.status,
        "a_key_level_materialization_task_id": key_level_task.id,
        "a_key_level_materialization_task_status": key_level_task.status,
        "followups": followups,
    }


def _enqueue_a_key_level_materialization(db: Session, *, trade_date: str, reason: str):
    return RuntimeTaskQueue(db).enqueue(
        RuntimeTaskCreate(
            task_type=A_KEY_LEVEL_MATERIALIZATION_TASK,
            payload={"trade_date": trade_date, "reason": reason},
            priority=45,
            idempotency_key=f"{A_KEY_LEVEL_MATERIALIZATION_TASK}:{trade_date}",
            max_attempts=3,
        )
    )


def enqueue_after_close_followups(
    db: Session,
    *,
    trade_date: str,
    now: datetime | None = None,
    strategies: list[str] | None = None,
    reason: str = "after_close_latest_data",
) -> dict[str, Any]:
    """Queue idempotent post-close artifacts once daily bars are complete."""

    current = now or beijing_now()
    if not trade_date:
        return {"ok": False, "reason": "missing_trade_date"}
    review_date = _parse_trade_date(trade_date)
    if not is_a_share_trading_day(review_date):
        return {"ok": True, "action": "skip_non_trading_day", "trade_date": trade_date}
    queue = RuntimeTaskQueue(db)
    required = sorted(strategies or PRODUCTION_PRIORITY_STRATEGIES)
    slots = _review_slots_for_trade_date(current=current, trade_date=trade_date)
    return {
        "ok": True,
        "trade_date": trade_date,
        "reason": reason,
        "market_review": enqueue_market_review_reports_if_missing(
            db,
            trade_date=trade_date,
            slots=slots,
            reason=reason,
            queue=queue,
        ),
        "paper_review": enqueue_paper_review_reports_if_missing(
            db,
            trade_date=trade_date,
            slots=slots,
            reason=reason,
            queue=queue,
        ),
        "data_quality_sla": _enqueue_daily_bar_sla_if_missing(
            db,
            trade_date=trade_date,
            reason=reason,
            queue=queue,
        ),
        "low_buy_close_review": _enqueue_low_buy_close_review_materialization(
            db,
            trade_date=trade_date,
            strategies=required,
            reason=reason,
            queue=queue,
        ),
    }


def enqueue_market_review_reports_if_missing(
    db: Session,
    *,
    trade_date: str,
    slots: list[str],
    reason: str,
    queue: RuntimeTaskQueue | None = None,
) -> list[dict[str, Any]]:
    review_date = _parse_trade_date(trade_date)
    active_queue = queue or RuntimeTaskQueue(db)
    results: list[dict[str, Any]] = []
    for slot in _normalized_slots(slots):
        if _market_review_exists(db, review_date, slot):
            results.append({"slot": slot, "action": "exists", "trade_date": trade_date})
            continue
        idempotency_key = f"{MARKET_REVIEW_TASK}:{trade_date}:{slot}"
        if _succeeded_task_exists(db, idempotency_key):
            results.append({"slot": slot, "action": "succeeded_task_exists", "trade_date": trade_date})
            continue
        task = active_queue.enqueue(
            RuntimeTaskCreate(
                task_type=MARKET_REVIEW_TASK,
                payload={"report_slot": slot, "target_date": trade_date, "reason": reason},
                priority=25 if slot == "close" else 30,
                idempotency_key=idempotency_key,
                max_attempts=3,
            )
        )
        results.append({"slot": slot, "action": "queued", "task_id": task.id, "task_status": task.status})
    return results


def enqueue_paper_review_reports_if_missing(
    db: Session,
    *,
    trade_date: str,
    slots: list[str],
    reason: str,
    queue: RuntimeTaskQueue | None = None,
) -> list[dict[str, Any]]:
    review_date = _parse_trade_date(trade_date)
    active_queue = queue or RuntimeTaskQueue(db)
    results: list[dict[str, Any]] = []
    for slot in _normalized_slots(slots):
        existing_count = _paper_review_count(db, review_date, slot)
        if existing_count > 0:
            results.append({"slot": slot, "action": "exists", "trade_date": trade_date, "existing_count": existing_count})
            continue
        idempotency_key = f"{PAPER_REVIEW_TASK}:{trade_date}:{slot}"
        if _succeeded_task_exists(db, idempotency_key):
            results.append({"slot": slot, "action": "succeeded_task_exists", "trade_date": trade_date})
            continue
        task = active_queue.enqueue(
            RuntimeTaskCreate(
                task_type=PAPER_REVIEW_TASK,
                payload={"report_slot": slot, "target_date": trade_date, "reason": reason},
                priority=28 if slot == "close" else 32,
                idempotency_key=idempotency_key,
                max_attempts=3,
            )
        )
        results.append({"slot": slot, "action": "queued", "task_id": task.id, "task_status": task.status})
    return results


def _enqueue_daily_bar_sla_if_missing(
    db: Session,
    *,
    trade_date: str,
    reason: str,
    queue: RuntimeTaskQueue,
) -> dict[str, Any]:
    review_date = _parse_trade_date(trade_date)
    if _daily_bar_sla_exists(db, review_date):
        return {"action": "exists", "trade_date": trade_date, "dataset_key": "daily_bars"}
    idempotency_key = f"{DATA_QUALITY_SLA_TASK}:daily_bars:production_universe:{trade_date}"
    if _succeeded_task_exists(db, idempotency_key):
        return {"action": "succeeded_task_exists", "trade_date": trade_date, "dataset_key": "daily_bars"}
    task = queue.enqueue(
        RuntimeTaskCreate(
            task_type=DATA_QUALITY_SLA_TASK,
            payload={
                "datasets": ["daily_bars"],
                "scope": "production_universe",
                "start_date": trade_date,
                "end_date": trade_date,
                "expected_days": 1,
                "reason": reason,
            },
            priority=22,
            idempotency_key=idempotency_key,
            max_attempts=3,
        )
    )
    return {"action": "queued", "task_id": task.id, "task_status": task.status, "dataset_key": "daily_bars"}


def _enqueue_low_buy_close_review_materialization(
    db: Session,
    *,
    trade_date: str,
    strategies: list[str],
    reason: str,
    queue: RuntimeTaskQueue,
) -> dict[str, Any]:
    required = sorted({item.strip() for item in strategies if item and item.strip()})
    if not required:
        return {"action": "skip", "reason": "missing_strategies", "trade_date": trade_date}
    idempotency_key = f"{LOW_BUY_MATERIALIZATION_TASK}:{trade_date}:close_review:{','.join(required)}"
    if _succeeded_task_exists(db, idempotency_key):
        return {"action": "succeeded_task_exists", "trade_date": trade_date, "strategies": required}
    task = queue.enqueue(
        RuntimeTaskCreate(
            task_type=LOW_BUY_MATERIALIZATION_TASK,
            payload={
                "expected_trade_date": trade_date,
                "strategies": required,
                "limit": 40,
                "scan_limit": 480,
                "reason": f"{reason}_close_review",
                "build_close_review": True,
            },
            priority=24,
            idempotency_key=idempotency_key,
            max_attempts=3,
        )
    )
    return {
        "action": "queued" if task.status != "succeeded" else "exists",
        "task_id": task.id,
        "task_status": task.status,
        "strategies": required,
    }


def _review_slots_for_time(current: datetime) -> list[str]:
    return _review_slots_for_trade_date(current=current)


def _review_slots_for_trade_date(*, current: datetime, trade_date: str | None = None) -> list[str]:
    if trade_date and _parse_trade_date(trade_date) < current.date():
        return ["midday", "close"]
    if current.time() >= _configured_close_review_time():
        return ["midday", "close"]
    if MIDDAY_REVIEW_AFTER <= current.time() < MIDDAY_REVIEW_BEFORE:
        return ["midday"]
    return []


def _configured_close_review_time() -> dt_time:
    from app.core.config import get_settings

    settings = get_settings()
    try:
        hour, minute = [int(part) for part in settings.paper_perf_archive_time.split(":", 1)]
        return dt_time(hour=hour, minute=minute)
    except (TypeError, ValueError):
        return DEFAULT_CLOSE_REVIEW_AFTER


def _market_review_exists(db: Session, review_date: date, slot: str) -> bool:
    return (
        db.execute(
            select(MarketReviewReport.id)
            .where(MarketReviewReport.report_date == review_date, MarketReviewReport.report_slot == slot)
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )


def _paper_review_count(db: Session, review_date: date, slot: str) -> int:
    return int(
        db.execute(
            select(func.count(PaperReviewReport.id)).where(
                PaperReviewReport.report_date == review_date,
                PaperReviewReport.report_slot == slot,
            )
        ).scalar()
        or 0
    )


def _daily_bar_sla_exists(db: Session, review_date: date) -> bool:
    return (
        db.execute(
            select(DataQualitySnapshot.id)
            .where(
                DataQualitySnapshot.dataset_key == "daily_bars",
                DataQualitySnapshot.scope == "production_universe",
                DataQualitySnapshot.as_of_date == review_date,
            )
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )


def _succeeded_task_exists(db: Session, idempotency_key: str) -> bool:
    return (
        db.execute(
            select(RuntimeTask.id)
            .where(RuntimeTask.idempotency_key == idempotency_key, RuntimeTask.status == "succeeded")
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )


def _normalized_slots(slots: list[str]) -> list[str]:
    normalized: list[str] = []
    for slot in slots:
        value = str(slot or "").strip().lower()
        if value not in {"midday", "close"} or value in normalized:
            continue
        normalized.append(value)
    return normalized


def _parse_trade_date(raw: str) -> date:
    return date.fromisoformat(str(raw)[:10])
