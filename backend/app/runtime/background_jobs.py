from __future__ import annotations

from datetime import date, datetime, time as dt_time
import fcntl
import logging
from pathlib import Path
import tempfile
import threading

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.task_manager import task_manager
from app.core.timezone import beijing_now, beijing_today
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.runtime.strategy_evolution_scheduler import (
    enqueue_monthly_drift_monitor_once,
    enqueue_strategy_self_evolution_once,
    start_strategy_evolution_scheduler,
    shutdown_strategy_evolution_scheduler,
)
from app.runtime.background_low_buy_cleanup import cleanup_stale_low_buy_snapshots
from app.repositories.low_buy.results import LowBuyResultRepository
from app.services.agent_daily_workflow_service import AgentDailyWorkflowService
from app.services.agent_notification_service import AgentNotificationService
from app.services.agent_signal_scan_service import AgentSignalScanService
from app.services.backtest_research_worker import BacktestResearchWorker
from app.services.latest_data_status import expected_low_buy_trade_date, publish_latest_trade_date_if_ready
from app.services.low_buy.shared import DEFAULT_PRODUCTION_LOW_BUY_STRATEGY
from app.services.low_buy.strategy_auto_governance import refresh_low_buy_strategy_auto_governance
from app.services.low_buy.strategy_policy import PRODUCTION_PRIORITY_STRATEGIES
from app.services.low_buy_screener import PLAYBOOKS, LowBuyScreenerService
from app.services.low_buy_materialization import enqueue_low_buy_materialization
from app.services.market_data import MarketDataService
from app.services.market_quote_cache_refresh import quote_cache_refresh_bucket, quote_cache_refresh_due
from app.services.paper.archive import PaperArchiveService
from app.services.paper.scheduler import build_auto_trader_config, start_auto_trader, stop_auto_trader
from app.services.paper.validation_scheduler import MonthlyStrategyValidationJob
from app.services.tasks import RuntimeTaskQueue
from app.services.watchlist_signal_service import WatchlistSignalService


settings = get_settings()
logger = logging.getLogger(__name__)

FULL_SCAN_REFRESH_SECONDS = 60 * 60
WATCHLIST_REFRESH_SECONDS = 45
MARKET_REGIME_REFRESH_SECONDS = 5 * 60
APP_LOW_BUY_STARTUP_LIMIT = 24
FULL_SCAN_BACKGROUND_LIMIT = 40
SQLITE_BACKGROUND_SCAN_LIMIT = 120
DEFAULT_BACKGROUND_SCAN_LIMIT = 480
ML_INCREMENTAL_TRAIN_WEEKDAY = 4  # Friday
ML_INCREMENTAL_TRAIN_AFTER = dt_time(hour=16, minute=0)
_paper_archive_last_run_date: date | None = None
_background_leader_lock_handle = None


def _background_jobs_enabled() -> bool:
    if not settings.runtime_background_jobs_enabled:
        return False
    if settings.database_url.startswith("sqlite") and not settings.runtime_background_jobs_on_sqlite:
        return False
    return True


def _background_low_buy_strategies() -> list[str]:
    if settings.database_url.startswith("sqlite"):
        return [strategy for strategy in PLAYBOOKS if strategy in PRODUCTION_PRIORITY_STRATEGIES]
    return list(PLAYBOOKS.keys())


def _background_low_buy_limit() -> int:
    if settings.database_url.startswith("sqlite"):
        return APP_LOW_BUY_STARTUP_LIMIT
    return FULL_SCAN_BACKGROUND_LIMIT


def _background_low_buy_scan_limit() -> int:
    if settings.database_url.startswith("sqlite"):
        return SQLITE_BACKGROUND_SCAN_LIMIT
    return DEFAULT_BACKGROUND_SCAN_LIMIT


def _startup_low_buy_prewarm_enabled() -> bool:
    return True


def _startup_low_buy_history_prewarm_enabled() -> bool:
    return not settings.database_url.startswith("sqlite")


def _refresh_materialized_low_buy_snapshots(
    *,
    strategies: list[str],
    limit: int,
    scan_limit: int,
    compute_performance: bool,
) -> None:
    screener = LowBuyScreenerService()
    for strategy_key in strategies:
        if _materialized_snapshot_is_fresh(
            screener=screener,
            strategy_key=strategy_key,
            limit=limit,
            max_age_seconds=FULL_SCAN_REFRESH_SECONDS,
        ):
            continue
        screener.refresh_full_scan_cache(
            strategy=strategy_key,
            limit=limit,
            scan_limit=scan_limit,
            include_history=False,
            compute_performance=compute_performance,
            build_close_review=False,
        )
    with SessionLocal() as db:
        publish_latest_trade_date_if_ready(db, strategies=sorted(PRODUCTION_PRIORITY_STRATEGIES))
        db.commit()


def _materialized_snapshot_is_fresh(
    *,
    screener: LowBuyScreenerService,
    strategy_key: str,
    limit: int,
    max_age_seconds: int,
) -> bool:
    with SessionLocal() as db:
        repository = LowBuyResultRepository(db)
        latest_available_trade_date = expected_low_buy_trade_date(db) or repository.fetch_latest_trade_date()
        payload = screener._runtime._load_latest_materialized_full_result(
            db=db,
            strategy=strategy_key,
            limit=limit,
            include_history=False,
            allow_repair=False,
        )
    if payload is None:
        return False
    if latest_available_trade_date and payload.latest_trade_date < latest_available_trade_date:
        return False
    try:
        updated_at = datetime.strptime(
            payload.full_scan_updated_at or payload.as_of_date,
            "%Y-%m-%d %H:%M:%S",
        )
    except ValueError:
        return False
    return (beijing_now().replace(tzinfo=None) - updated_at).total_seconds() < max_age_seconds


def _warm_runtime_caches() -> None:
    db = SessionLocal()
    watchlist_signal_service = WatchlistSignalService()
    try:
        _warm_market_regime_once()
        if _startup_low_buy_prewarm_enabled():
            _refresh_materialized_low_buy_snapshots(
                strategies=_background_low_buy_strategies(),
                limit=_background_low_buy_limit(),
                scan_limit=_background_low_buy_scan_limit(),
                compute_performance=True,
            )
        if _startup_low_buy_history_prewarm_enabled():
            screener = LowBuyScreenerService()
            screener.history(db=db, strategy=DEFAULT_PRODUCTION_LOW_BUY_STRATEGY)
        watchlist_signal_service.refresh_snapshots(force=True)
    except Exception:
        logger.exception("runtime cache prewarm failed")
    finally:
        db.close()


def _startup_maintenance_and_warm_runtime_caches() -> None:
    try:
        cleanup_stale_low_buy_snapshots()
    except Exception:
        logger.exception("stale low-buy snapshot cleanup failed")
    _warm_runtime_caches()


def _refresh_full_scan_once() -> None:
    _refresh_materialized_low_buy_snapshots(
        strategies=_background_low_buy_strategies(),
        limit=_background_low_buy_limit(),
        scan_limit=_background_low_buy_scan_limit(),
        compute_performance=True,
    )


def _refresh_watchlist_signal_once() -> None:
    watchlist_signal_service = WatchlistSignalService()
    watchlist_signal_service.refresh_snapshots(force=True)


def _warm_market_regime_once() -> None:
    MarketDataService().get_market_regime()


def _archive_paper_performance_once() -> None:
    global _paper_archive_last_run_date
    if not _paper_archive_due():
        return
    today = beijing_today()
    if _paper_archive_last_run_date == today:
        return
    with SessionLocal() as db:
        service = PaperArchiveService(db)
        results = service.archive_all_active(include_report=settings.paper_perf_ai_report_enabled)
        _paper_archive_last_run_date = today
        logger.info("模拟盘绩效归档完成: %s", results)


def _run_monthly_strategy_validation_once() -> None:
    if settings.database_url.startswith("sqlite"):
        return
    with SessionLocal() as db:
        report = MonthlyStrategyValidationJob(db).run_if_due()
        if report is not None:
            logger.info("月度策略样本外验证完成: run_id=%s", report.run_id)


def _run_backtest_research_worker_once() -> None:
    result = BacktestResearchWorker().run_once()
    if result is not None:
        logger.info(
            "回测研究任务处理完成: kind=%s id=%s status=%s message=%s",
            result.task_kind,
            result.task_id,
            result.status,
            result.message,
        )


def _refresh_low_buy_strategy_governance_once() -> None:
    if settings.database_url.startswith("sqlite"):
        return
    with SessionLocal() as db:
        payload = refresh_low_buy_strategy_auto_governance(db)
        logger.info("低吸策略自动治理刷新完成: items=%s", len(payload.get("items", {})))


def _scan_priority_notifications_once() -> None:
    if not settings.notification_signal_scan_enabled:
        return
    notifier = AgentNotificationService()
    if not notifier.supports_channel("feishu"):
        return
    with SessionLocal() as db:
        result = AgentSignalScanService(notifier).scan_priority_board(db, limit=12, channel="feishu")
        logger.info(
            "优先级榜通知扫描完成: scanned=%s sent=%s suppressed=%s upgraded=%s",
            result.scanned,
            result.sent,
            result.suppressed,
            result.upgraded,
        )


def _push_agent_daily_report_once() -> None:
    if not _agent_daily_report_push_due():
        return
    notifier = AgentNotificationService()
    if not notifier.supports_channel("feishu"):
        return
    with SessionLocal() as db:
        result = AgentDailyWorkflowService(notification_service=notifier).push_daily_report(db, channel="feishu")
        logger.info(
            "Agent 日报推送检查完成: trade_date=%s sent=%s duplicate=%s message=%s",
            result.trade_date,
            result.sent,
            result.duplicate,
            result.message,
        )


def _enqueue_ml_incremental_train_once() -> None:
    enqueue_strategy_self_evolution_once(beijing_now())


def _ml_incremental_train_due(now: datetime) -> bool:
    """Online learning runs after Friday close so the week's paper outcomes are settled."""

    return now.weekday() == ML_INCREMENTAL_TRAIN_WEEKDAY and now.time() >= ML_INCREMENTAL_TRAIN_AFTER


def _enqueue_market_quote_cache_refresh_once() -> None:
    if not quote_cache_refresh_due():
        return
    bucket = quote_cache_refresh_bucket()
    with SessionLocal() as db:
        task = RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
                task_type="market_quote_cache_refresh",
                payload={"limit": 200},
                priority=40,
                idempotency_key=f"market_quote_cache_refresh:{bucket}",
                max_attempts=2,
            )
        )
        logger.info("本地行情缓存预热任务检查完成: bucket=%s task_id=%s status=%s", bucket, task.id, task.status)


def _enqueue_low_buy_materialization_once() -> None:
    now = beijing_now()
    if now.weekday() >= 5 or now.time() < dt_time(hour=15, minute=10):
        return
    with SessionLocal() as db:
        enqueue_low_buy_materialization(db, reason="scheduled_after_close")
        db.commit()


def _enqueue_daily_bar_refresh_once() -> None:
    now = beijing_now()
    if now.weekday() >= 5 or now.time() < dt_time(hour=15, minute=10):
        return
    bucket = now.strftime("%Y%m%d%H%M")
    with SessionLocal() as db:
        task = RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
                task_type="daily_bar_refresh",
                payload={"limit": 6000},
                priority=30,
                idempotency_key=f"daily_bar_refresh:{bucket}",
                max_attempts=2,
            )
        )
        logger.info("日线快照刷新任务检查完成: bucket=%s task_id=%s status=%s", bucket, task.id, task.status)


def _paper_archive_due() -> bool:
    try:
        hour, minute = [int(part) for part in settings.paper_perf_archive_time.split(":", 1)]
        archive_time = dt_time(hour=hour, minute=minute)
    except (TypeError, ValueError):
        logger.warning("PAPER_PERF_ARCHIVE_TIME 配置无效: %s", settings.paper_perf_archive_time)
        archive_time = dt_time(hour=15, minute=5)
    return beijing_now().time() >= archive_time


def _agent_daily_report_push_due() -> bool:
    now = beijing_now()
    if now.weekday() >= 5:
        return False
    return now.time() >= dt_time(hour=15, minute=10)


def _acquire_background_leader_lock() -> bool:
    """Ensure only one Gunicorn worker runs in-process background jobs."""

    global _background_leader_lock_handle
    lock_path = Path(tempfile.gettempdir()) / "tquant_runtime_background_jobs.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return False
    except OSError:
        handle.close()
        logger.exception("failed to acquire runtime background leader lock")
        return False
    _background_leader_lock_handle = handle
    return True


def start_runtime_background_jobs() -> None:
    background_leader = _background_jobs_enabled() and _acquire_background_leader_lock()
    if background_leader:
        start_strategy_evolution_scheduler()
        threading.Thread(target=_startup_maintenance_and_warm_runtime_caches, daemon=True).start()
        task_manager.register_loop(
            name="low_buy_full_scan",
            target=_refresh_full_scan_once,
            interval_seconds=FULL_SCAN_REFRESH_SECONDS,
            initial_delay_seconds=30,
        )
        task_manager.register_loop(
            name="watchlist_signals",
            target=_refresh_watchlist_signal_once,
            interval_seconds=WATCHLIST_REFRESH_SECONDS,
            initial_delay_seconds=20,
        )
        task_manager.register_loop(
            name="market_regime_prewarm",
            target=_warm_market_regime_once,
            interval_seconds=MARKET_REGIME_REFRESH_SECONDS,
            initial_delay_seconds=15,
        )
        task_manager.register_loop(
            name="market_quote_cache_refresh",
            target=_enqueue_market_quote_cache_refresh_once,
            interval_seconds=30,
            initial_delay_seconds=10,
        )
        task_manager.register_loop(
            name="low_buy_materialization_refresh",
            target=_enqueue_low_buy_materialization_once,
            interval_seconds=300,
            initial_delay_seconds=60,
        )
        task_manager.register_loop(
            name="daily_bar_refresh",
            target=_enqueue_daily_bar_refresh_once,
            interval_seconds=300,
            initial_delay_seconds=45,
        )
        if settings.paper_perf_archive_enabled:
            task_manager.register_loop(
                name="paper_perf_archive",
                target=_archive_paper_performance_once,
                interval_seconds=300,
                initial_delay_seconds=90,
            )
        if settings.strategy_validation_monthly_enabled:
            task_manager.register_loop(
                name="strategy_validation_monthly",
                target=_run_monthly_strategy_validation_once,
                interval_seconds=24 * 60 * 60,
                initial_delay_seconds=180,
            )
        task_manager.register_loop(
            name="backtest_research_worker",
            target=_run_backtest_research_worker_once,
            interval_seconds=15,
            initial_delay_seconds=45,
        )
        task_manager.register_loop(
            name="low_buy_strategy_governance",
            target=_refresh_low_buy_strategy_governance_once,
            interval_seconds=60 * 60,
            initial_delay_seconds=210,
        )
        if settings.notification_signal_scan_enabled:
            task_manager.register_loop(
                name="agent_priority_notifications",
                target=_scan_priority_notifications_once,
                interval_seconds=max(settings.notification_signal_scan_interval_seconds, 30),
                initial_delay_seconds=120,
            )
        task_manager.register_loop(
            name="agent_daily_report_push",
            target=_push_agent_daily_report_once,
            interval_seconds=300,
            initial_delay_seconds=150,
        )
        task_manager.register_loop(
            name="ml_signal_incremental_train_weekly",
            target=_enqueue_ml_incremental_train_once,
            interval_seconds=60 * 60,
            initial_delay_seconds=240,
        )
        task_manager.register_loop(
            name="ml_feature_drift_monitor_monthly",
            target=enqueue_monthly_drift_monitor_once,
            interval_seconds=60 * 60,
            initial_delay_seconds=300,
        )
        if settings.paper_auto_trading_enabled:
            logger.info("启动模拟盘自动交易")
            start_auto_trader(build_auto_trader_config(settings))
    elif _background_jobs_enabled():
        logger.info("runtime background jobs skipped in this worker; another worker holds the leader lock")


def shutdown_runtime_background_jobs(timeout: int = 30) -> None:
    stop_auto_trader()
    shutdown_strategy_evolution_scheduler()
    task_manager.shutdown(timeout=timeout)
