from __future__ import annotations

import logging
from datetime import datetime, time as dt_time
from typing import Any

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.timezone import BEIJING_TZ, beijing_now
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.tasks import RuntimeTaskQueue

logger = logging.getLogger(__name__)

try:  # APScheduler is optional during lightweight local tests.
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
except Exception:  # pragma: no cover - exercised only when dependency missing.
    BackgroundScheduler = None  # type: ignore[assignment]
    CronTrigger = None  # type: ignore[assignment]

_scheduler: Any | None = None


def _self_evolution_due_time() -> dt_time:
    settings = get_settings()
    return dt_time(hour=settings.evolution_scheduler_hour, minute=settings.evolution_due_minute)


def _monthly_drift_due_time() -> dt_time:
    settings = get_settings()
    return dt_time(hour=settings.evolution_drift_scheduler_hour, minute=settings.evolution_drift_due_minute)


def self_evolution_due(now: datetime) -> bool:
    settings = get_settings()
    return now.weekday() == settings.evolution_scheduler_weekday and now.time() >= _self_evolution_due_time()


def enqueue_strategy_self_evolution_once(now: datetime | None = None) -> Any | None:
    logger.debug("策略自进化依赖模拟盘样本，模拟盘功能已下线，跳过任务入队。")
    return None


def enqueue_monthly_drift_monitor_once(now: datetime | None = None) -> Any | None:
    now = now or beijing_now()
    settings = get_settings()
    if now.day != settings.evolution_drift_scheduler_day or now.time() < _monthly_drift_due_time():
        return None
    bucket = now.strftime("%Y%m")
    with SessionLocal() as db:
        task = RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
                task_type="ml_feature_drift_monitor",
                payload={"min_samples": 100},
                priority=150,
                idempotency_key=f"ml_feature_drift_monitor:{bucket}",
                max_attempts=2,
            )
        )
        logger.info("ML 特征漂移月度任务检查完成: bucket=%s task_id=%s status=%s", bucket, task.id, task.status)
        return task


def start_strategy_evolution_scheduler() -> bool:
    global _scheduler
    settings = get_settings()
    if BackgroundScheduler is None or CronTrigger is None:
        logger.warning("APScheduler 未安装，策略自进化仅使用 runtime loop 兜底调度。")
        return False
    if _scheduler is not None and _scheduler.running:
        return True
    scheduler = BackgroundScheduler(timezone=BEIJING_TZ)
    scheduler.add_job(
        enqueue_monthly_drift_monitor_once,
        CronTrigger(
            day=settings.evolution_drift_scheduler_day,
            hour=settings.evolution_drift_scheduler_hour,
            minute=settings.evolution_drift_scheduler_minute,
            timezone=BEIJING_TZ,
        ),
        id="ml_feature_drift_monitor_monthly",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("APScheduler ML 漂移监控调度已启动")
    return True


def shutdown_strategy_evolution_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
