from __future__ import annotations

import logging
from datetime import datetime, time as dt_time
from typing import Any

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
SELF_EVOLUTION_WEEKDAY = 4
SELF_EVOLUTION_AFTER = dt_time(hour=16, minute=0)


def self_evolution_due(now: datetime) -> bool:
    return now.weekday() == SELF_EVOLUTION_WEEKDAY and now.time() >= SELF_EVOLUTION_AFTER


def enqueue_strategy_self_evolution_once(now: datetime | None = None) -> Any | None:
    now = now or beijing_now()
    if not self_evolution_due(now):
        return None
    week_key = f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"
    with SessionLocal() as db:
        task = RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
                task_type="strategy_self_evolution",
                payload={
                    "model_type": "xgboost",
                    "source": "paper",
                    "limit": 5000,
                    "min_samples": 100,
                    "warm_start": True,
                    "max_validation_p_value": 0.05,
                    "operator": "weekly-self-evolution",
                },
                priority=180,
                idempotency_key=f"strategy_self_evolution:{week_key}",
                max_attempts=2,
            )
        )
        logger.info("策略自进化任务检查完成: week=%s task_id=%s status=%s", week_key, task.id, task.status)
        return task


def enqueue_monthly_drift_monitor_once(now: datetime | None = None) -> Any | None:
    now = now or beijing_now()
    if now.day != 1 or now.time() < dt_time(hour=16, minute=30):
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
    if BackgroundScheduler is None or CronTrigger is None:
        logger.warning("APScheduler 未安装，策略自进化仅使用 runtime loop 兜底调度。")
        return False
    if _scheduler is not None and _scheduler.running:
        return True
    scheduler = BackgroundScheduler(timezone=BEIJING_TZ)
    scheduler.add_job(
        enqueue_strategy_self_evolution_once,
        CronTrigger(day_of_week="fri", hour=16, minute=5, timezone=BEIJING_TZ),
        id="strategy_self_evolution_weekly",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        enqueue_monthly_drift_monitor_once,
        CronTrigger(day=1, hour=16, minute=35, timezone=BEIJING_TZ),
        id="ml_feature_drift_monitor_monthly",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("APScheduler 策略自进化调度已启动")
    return True


def shutdown_strategy_evolution_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
