from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import RuntimeTask, SystemSetting

HEARTBEAT_SETTING_KEY = "runtime_worker.heartbeat"
HEARTBEAT_STALE_SECONDS = 120
CRITICAL_QUEUE_BLOCK_SECONDS = 600
CRITICAL_TASK_TYPES = {
    "daily_bar_refresh",
    "low_buy_materialization_refresh",
    "strategy_tracking_snapshot_refresh",
    "a_key_level_materialization_refresh",
    "monitor_snapshot_refresh",
}


def record_runtime_worker_heartbeat(
    db: Session,
    *,
    worker_id: str,
    now: datetime | None = None,
    status: str = "running",
) -> None:
    current = now or datetime.utcnow()
    payload = {
        "worker_id": str(worker_id or ""),
        "updated_at": current.isoformat(timespec="seconds"),
        "status": status,
    }
    raw = json.dumps(payload, ensure_ascii=False)
    row = db.execute(select(SystemSetting).where(SystemSetting.key == HEARTBEAT_SETTING_KEY)).scalar_one_or_none()
    if row is None:
        db.add(SystemSetting(key=HEARTBEAT_SETTING_KEY, value=raw))
    else:
        row.value = raw
    db.commit()


def build_runtime_fallback_status(db: Session, *, now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.utcnow()
    heartbeat = _load_heartbeat(db)
    heartbeat_at = _parse_datetime(str(heartbeat.get("updated_at") or ""))
    heartbeat_age = _age_seconds(current, heartbeat_at)
    worker_status = _worker_status(heartbeat=heartbeat, heartbeat_age=heartbeat_age)
    critical = _critical_queue_status(db, now=current)
    blocking = worker_status != "running" or bool(critical["blocking"])
    return {
        "worker_status": worker_status,
        "worker_id": str(heartbeat.get("worker_id") or ""),
        "heartbeat_updated_at": heartbeat_at.isoformat(timespec="seconds") if heartbeat_at else "",
        "heartbeat_age_seconds": heartbeat_age,
        "critical_queued_count": critical["count"],
        "oldest_critical_queued_at": critical["oldest_at"],
        "oldest_critical_queued_age_seconds": critical["oldest_age_seconds"],
        "blocking": blocking,
        "message": _message(worker_status=worker_status, critical=critical),
        "recovery_actions": _recovery_actions(worker_status=worker_status, critical=critical),
    }


def _load_heartbeat(db: Session) -> dict[str, Any]:
    row = db.execute(select(SystemSetting).where(SystemSetting.key == HEARTBEAT_SETTING_KEY)).scalar_one_or_none()
    if row is None or not row.value:
        return {}
    try:
        loaded = json.loads(row.value)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _worker_status(*, heartbeat: dict[str, Any], heartbeat_age: int | None) -> str:
    if not heartbeat or heartbeat_age is None:
        return "missing"
    if heartbeat_age > HEARTBEAT_STALE_SECONDS:
        return "stale"
    return "running"


def _critical_queue_status(db: Session, *, now: datetime) -> dict[str, Any]:
    base = (
        select(RuntimeTask)
        .where(RuntimeTask.task_type.in_(sorted(CRITICAL_TASK_TYPES)))
        .where(RuntimeTask.status == "queued")
    )
    count = int(db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0)
    oldest = db.execute(base.order_by(RuntimeTask.created_at.asc(), RuntimeTask.id.asc()).limit(1)).scalar_one_or_none()
    oldest_at = oldest.created_at if oldest is not None else None
    oldest_age = _age_seconds(now, oldest_at)
    return {
        "count": count,
        "oldest_at": oldest_at.isoformat(timespec="seconds") if oldest_at else "",
        "oldest_age_seconds": oldest_age,
        "blocking": oldest_age is not None and oldest_age >= CRITICAL_QUEUE_BLOCK_SECONDS,
    }


def _parse_datetime(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _age_seconds(now: datetime, value: datetime | None) -> int | None:
    if value is None:
        return None
    return max(0, int((now.replace(tzinfo=None) - value.replace(tzinfo=None)).total_seconds()))


def _message(*, worker_status: str, critical: dict[str, Any]) -> str:
    if worker_status == "missing":
        return "runtime worker heartbeat missing"
    if worker_status == "stale":
        return "runtime worker heartbeat stale"
    if critical["blocking"]:
        return "critical runtime refresh tasks queued for too long"
    return "runtime worker running and critical refresh queue is clear"


def _recovery_actions(*, worker_status: str, critical: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    if worker_status in {"missing", "stale"}:
        actions.extend(["启动或重启 runtime-worker", "检查 runtime-worker 日志和数据库连接"])
    if critical["blocking"]:
        actions.extend(["检查 runtime_tasks 中排队超过 10 分钟的关键刷新任务", "确认 runtime-scheduler 没有重复入队同一批关键任务"])
    if not actions:
        actions.append("继续观察，无需人工处理")
    return actions
