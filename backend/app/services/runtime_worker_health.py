from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import RuntimeTask, SystemSetting

HEARTBEAT_SETTING_KEY = "runtime_worker.heartbeat"
COMPONENT_HEARTBEAT_PREFIX = "platform_component.heartbeat."
HEARTBEAT_STALE_SECONDS = 120
CRITICAL_QUEUE_BLOCK_SECONDS = 600
CRITICAL_TASK_TYPES = {
    "daily_bar_refresh",
    "low_buy_materialization_refresh",
    "strategy_tracking_snapshot_refresh",
    "a_key_level_materialization_refresh",
    "monitor_snapshot_refresh",
}
DEFAULT_OBSERVED_COMPONENTS = ("runtime-worker", "runtime-scheduler", "analytics-worker", "backtest-worker")


def record_runtime_worker_heartbeat(
    db: Session,
    *,
    worker_id: str,
    now: datetime | None = None,
    status: str = "running",
) -> None:
    record_platform_component_heartbeat(db, component="runtime-worker", worker_id=worker_id, now=now, status=status)


def record_platform_component_heartbeat(
    db: Session,
    *,
    component: str,
    worker_id: str,
    now: datetime | None = None,
    status: str = "running",
) -> None:
    current = now or datetime.utcnow()
    component_name = _normalize_component(component)
    payload = {
        "component": component_name,
        "worker_id": str(worker_id or ""),
        "updated_at": current.isoformat(timespec="seconds"),
        "status": status,
    }
    raw = json.dumps(payload, ensure_ascii=False)
    _upsert_setting(db, _component_heartbeat_key(component_name), raw)
    if component_name == "runtime-worker":
        _upsert_setting(db, HEARTBEAT_SETTING_KEY, raw)
    db.commit()


def platform_component_heartbeats(
    db: Session,
    *,
    now: datetime | None = None,
    components: tuple[str, ...] = DEFAULT_OBSERVED_COMPONENTS,
) -> list[dict[str, Any]]:
    current = now or datetime.utcnow()
    items: list[dict[str, Any]] = []
    for component in components:
        component_name = _normalize_component(component)
        payload = _load_component_heartbeat(db, component_name)
        heartbeat_at = _parse_datetime(str(payload.get("updated_at") or ""))
        age = _age_seconds(current, heartbeat_at)
        status = _worker_status(heartbeat=payload, heartbeat_age=age)
        items.append(
            {
                "component": component_name,
                "worker_id": str(payload.get("worker_id") or component_name),
                "status": status,
                "updated_at": heartbeat_at.isoformat(timespec="seconds") if heartbeat_at else "",
                "age_seconds": age,
            }
        )
    return items


def _upsert_setting(db: Session, key: str, value: str) -> None:
    row = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
    if row is None:
        db.add(SystemSetting(key=key, value=value))
        return
    row.value = value


def _component_heartbeat_key(component: str) -> str:
    return f"{COMPONENT_HEARTBEAT_PREFIX}{_normalize_component(component)}"


def _normalize_component(component: str) -> str:
    return str(component or "").strip() or "unknown"


def _load_component_heartbeat(db: Session, component: str) -> dict[str, Any]:
    row = db.execute(select(SystemSetting).where(SystemSetting.key == _component_heartbeat_key(component))).scalar_one_or_none()
    if row is None and component == "runtime-worker":
        row = db.execute(select(SystemSetting).where(SystemSetting.key == HEARTBEAT_SETTING_KEY)).scalar_one_or_none()
    if row is None or not row.value:
        return {}
    try:
        loaded = json.loads(row.value)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


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
