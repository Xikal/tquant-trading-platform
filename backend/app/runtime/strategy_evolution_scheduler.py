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


def _ledger_reconcile_due_time() -> dt_time:
    settings = get_settings()
    return dt_time(hour=settings.evolution_ledger_scheduler_hour, minute=settings.evolution_ledger_due_minute)


def self_evolution_due(now: datetime) -> bool:
    settings = get_settings()
    return now.weekday() == settings.evolution_scheduler_weekday and now.time() >= _self_evolution_due_time()


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


def enqueue_daily_ledger_reconcile_preview_once(now: datetime | None = None) -> Any | None:
    now = now or beijing_now()
    if now.weekday() >= 5 or now.time() < _ledger_reconcile_due_time():
        return None
    bucket = now.strftime("%Y%m%d")
    with SessionLocal() as db:
        task = RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
                task_type="paper_ledger_reconcile_preview",
                payload={
                    "threshold": float(get_settings().evolution_ledger_gap_alert_threshold),
                    "channel": "feishu",
                },
                priority=140,
                idempotency_key=f"paper_ledger_reconcile_preview:{bucket}",
                max_attempts=2,
            )
        )
        logger.info("模拟盘账本预检任务检查完成: bucket=%s task_id=%s status=%s", bucket, task.id, task.status)
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
        enqueue_strategy_self_evolution_once,
        CronTrigger(
            day_of_week=settings.evolution_scheduler_weekday,
            hour=settings.evolution_scheduler_hour,
            minute=settings.evolution_scheduler_minute,
            timezone=BEIJING_TZ,
        ),
        id="strategy_self_evolution_weekly",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
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
    scheduler.add_job(
        enqueue_daily_ledger_reconcile_preview_once,
        CronTrigger(
            day_of_week="mon-fri",
            hour=settings.evolution_ledger_scheduler_hour,
            minute=settings.evolution_ledger_scheduler_minute,
            timezone=BEIJING_TZ,
        ),
        id="paper_ledger_reconcile_preview_daily",
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
