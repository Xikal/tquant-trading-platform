from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime, time as dt_time
import fcntl
import json
import logging
from pathlib import Path
import tempfile
import threading
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse
from sqlalchemy import delete, select

from app.agent_tools.audit import agent_audit_metrics
from app.api.router import api_router
from app.api.routes.strategy_stream import ws_router as strategy_ws_router
from app.core.admin_auth import require_admin_auth
from app.core.config import get_settings
from app.core.database import SessionLocal, init_db, ping_database
from app.core.logging_config import configure_logging
from app.core.rate_limit import is_global_rate_allowed
from app.core.task_manager import task_manager
from app.core.timezone import beijing_now, beijing_today
from app.core.timing import record_request_timing, request_timing_snapshot
from app.models.entities import LowBuyResultSnapshot, LowBuyScanSnapshot
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.models.schemas import HealthResponse, ReadinessResponse
from app.repositories.low_buy.results import LowBuyResultRepository
from app.services.low_buy.shared import DEFAULT_PRODUCTION_LOW_BUY_STRATEGY, LOW_BUY_RESULT_VERSION
from app.services.low_buy.strategy_auto_governance import refresh_low_buy_strategy_auto_governance
from app.services.low_buy.strategy_policy import PRODUCTION_PRIORITY_STRATEGIES
from app.services.low_buy_screener import PLAYBOOKS, LowBuyScreenerService
from app.services.market_data import MarketDataService
from app.services.paper.archive import PaperArchiveService
from app.services.paper.scheduler import build_auto_trader_config, start_auto_trader, stop_auto_trader
from app.services.paper.validation_scheduler import MonthlyStrategyValidationJob
from app.services.auth_service import ensure_auth_secret_configured
from app.services.agent_daily_workflow_service import AgentDailyWorkflowService
from app.services.agent_notification_service import AgentNotificationService
from app.services.agent_signal_scan_service import AgentSignalScanService
from app.services.backtest_research_worker import BacktestResearchWorker
from app.services.watchlist_signal_service import WatchlistSignalService
from app.services.tasks import RuntimeTaskQueue

settings = get_settings()
configure_logging(structured=settings.structured_logs)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"
FRONTEND_INDEX_FILE = FRONTEND_DIST_DIR / "index.html"
FULL_SCAN_REFRESH_SECONDS = 60 * 60
WATCHLIST_REFRESH_SECONDS = 45
MARKET_REGIME_REFRESH_SECONDS = 5 * 60
APP_LOW_BUY_STARTUP_LIMIT = 24
FULL_SCAN_BACKGROUND_LIMIT = 40
SQLITE_BACKGROUND_SCAN_LIMIT = 120
DEFAULT_BACKGROUND_SCAN_LIMIT = 480
logger = logging.getLogger(__name__)
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


def _materialized_snapshot_is_fresh(
    *,
    screener: LowBuyScreenerService,
    strategy_key: str,
    limit: int,
    max_age_seconds: int,
) -> bool:
    with SessionLocal() as db:
        repository = LowBuyResultRepository(db)
        latest_available_trade_date = repository.fetch_latest_trade_date()
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
        _cleanup_stale_low_buy_snapshots()
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
    now = beijing_now()
    if now.weekday() != 0 or now.time() < dt_time(hour=16, minute=0):
        return
    week_key = f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"
    with SessionLocal() as db:
        task = RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
                task_type="ml_signal_incremental_train",
                payload={
                    "model_type": "logistic",
                    "source": "paper",
                    "limit": 5000,
                    "min_samples": 100,
                    "promote": False,
                },
                priority=180,
                idempotency_key=f"ml_signal_incremental_train:{week_key}",
                max_attempts=2,
            )
        )
        logger.info("ML 增量训练任务检查完成: week=%s task_id=%s status=%s", week_key, task.id, task.status)


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


def _cleanup_stale_low_buy_snapshots() -> None:
    """Remove materialized low-buy rows produced by older strategy versions."""
    with SessionLocal() as db:
        result_ids = _stale_low_buy_result_ids(db)
        scan_ids = _stale_low_buy_scan_ids(db)
        if result_ids:
            _delete_low_buy_rows(db, LowBuyResultSnapshot, result_ids)
        if scan_ids:
            _delete_low_buy_rows(db, LowBuyScanSnapshot, scan_ids)
        db.commit()
    if result_ids or scan_ids:
        logger.info(
            "cleaned stale low-buy snapshots: %d results + %d scans removed",
            len(result_ids),
            len(scan_ids),
        )


def _stale_low_buy_result_ids(db) -> list[int]:
    return _stale_snapshot_ids(
        db=db,
        model=LowBuyResultSnapshot,
        json_column=LowBuyResultSnapshot.payload_json,
        version_key="payload_version",
    )


def _stale_low_buy_scan_ids(db) -> list[int]:
    return _stale_snapshot_ids(
        db=db,
        model=LowBuyScanSnapshot,
        json_column=LowBuyScanSnapshot.filters_json,
        version_key="_result_version",
    )


def _stale_snapshot_ids(db, model, json_column, version_key: str, batch_size: int = 1000) -> list[int]:
    stale_ids: list[int] = []
    last_id = 0
    while True:
        rows = db.execute(
            select(model.id, json_column)
            .where(model.id > last_id)
            .order_by(model.id.asc())
            .limit(batch_size)
        ).all()
        if not rows:
            break
        last_id = int(rows[-1][0])
        stale_ids.extend(
            int(row_id)
            for row_id, raw_json in rows
            if _json_version(raw_json, version_key) != LOW_BUY_RESULT_VERSION
        )
    return stale_ids


def _delete_low_buy_rows(db, model, row_ids: list[int]) -> None:
    for index in range(0, len(row_ids), 500):
        chunk = row_ids[index : index + 500]
        db.execute(delete(model).where(model.id.in_(chunk)))


def _json_version(raw: str | None, key: str) -> int | None:
    try:
        payload = json.loads(raw or "{}")
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    value = payload.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


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


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_auth_secret_configured()
    init_db()
    background_leader = _background_jobs_enabled() and _acquire_background_leader_lock()
    if background_leader:
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
        if settings.paper_auto_trading_enabled:
            logger.info("启动模拟盘自动交易")
            start_auto_trader(build_auto_trader_config(settings))
    elif _background_jobs_enabled():
        logger.info("runtime background jobs skipped in this worker; another worker holds the leader lock")
    try:
        yield
    finally:
        stop_auto_trader()
        task_manager.shutdown(timeout=30)


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_prefix)
app.include_router(strategy_ws_router)


@app.middleware("http")
async def enforce_request_body_limit(request, call_next):
    if not is_global_rate_allowed(request):
        return JSONResponse(status_code=429, content={"detail": "请求过于频繁，请稍后再试。"})
    if request.method in {"POST", "PUT", "PATCH"}:
        content_length = request.headers.get("content-length")
        if content_length and _content_length_exceeds_limit(content_length):
            return JSONResponse(status_code=413, content={"detail": "请求体过大"})
    return await call_next(request)


@app.middleware("http")
async def record_http_timing(request, call_next):
    trace_id = request.headers.get("x-request-id") or f"req_{uuid4().hex}"
    request.state.trace_id = trace_id
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = trace_id
        return response
    finally:
        duration_ms = int((time.perf_counter() - started) * 1000)
        record_request_timing(
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_ms=duration_ms,
        )
        if duration_ms >= 3000:
            logger.warning(
                "slow_http_request trace_id=%s method=%s path=%s status=%s duration_ms=%s",
                trace_id,
                request.method,
                request.url.path,
                status_code,
                duration_ms,
            )


def _content_length_exceeds_limit(raw_value: str) -> bool:
    try:
        return int(raw_value) > settings.max_request_body_bytes
    except (TypeError, ValueError):
        return False


def _agent_audit_metrics_snapshot() -> dict[str, int]:
    try:
        with SessionLocal() as db:
            return agent_audit_metrics(db)
    except Exception:
        logger.warning("agent audit metrics unavailable")
        return {"calls_total": 0, "success_total": 0, "failure_total": 0}


def _phase4_metrics_snapshot() -> dict[str, int]:
    try:
        from sqlalchemy import func, select

        from app.models.entities import AgentResultQuality, RuntimeTask

        with SessionLocal() as db:
            queued = int(db.execute(select(func.count(RuntimeTask.id)).where(RuntimeTask.status == "queued")).scalar() or 0)
            running = int(db.execute(select(func.count(RuntimeTask.id)).where(RuntimeTask.status == "running")).scalar() or 0)
            failed = int(db.execute(select(func.count(RuntimeTask.id)).where(RuntimeTask.status == "failed")).scalar() or 0)
            low_quality = int(
                db.execute(select(func.count(AgentResultQuality.id)).where(AgentResultQuality.passed.is_(False))).scalar()
                or 0
            )
        return {
            "runtime_tasks_queued": queued,
            "runtime_tasks_running": running,
            "runtime_tasks_failed": failed,
            "agent_quality_blocked_total": low_quality,
        }
    except Exception:
        logger.warning("phase4 metrics unavailable")
        return {
            "runtime_tasks_queued": 0,
            "runtime_tasks_running": 0,
            "runtime_tasks_failed": 0,
            "agent_quality_blocked_total": 0,
        }


@app.get("/healthz", response_model=HealthResponse)
def healthz():
    return HealthResponse(status="ok", app=settings.app_name)


@app.get("/readyz", response_model=ReadinessResponse)
def readyz(response: Response):
    checks = {
        "database": False,
        "frontend_dist": FRONTEND_INDEX_FILE.exists(),
    }
    errors: list[str] = []

    try:
        ping_database()
        checks["database"] = True
    except Exception as exc:
        errors.append(f"database: {exc}")

    if not checks["frontend_dist"]:
        errors.append("frontend_dist: missing frontend/dist/index.html")

    if not all(checks.values()):
        response.status_code = 503
        return ReadinessResponse(
            status="degraded",
            app=settings.app_name,
            checks=checks,
            errors=errors,
        )

    return ReadinessResponse(status="ok", app=settings.app_name, checks=checks, errors=errors)


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics(_: None = Depends(require_admin_auth)) -> PlainTextResponse:
    snapshot = request_timing_snapshot()
    agent_snapshot = _agent_audit_metrics_snapshot()
    phase4_snapshot = _phase4_metrics_snapshot()
    lines = [
        "# HELP tquant_http_timing_samples Number of retained HTTP timing samples.",
        "# TYPE tquant_http_timing_samples gauge",
        f"tquant_http_timing_samples {snapshot.get('sample_count', 0)}",
        "# HELP tquant_http_p95_ms Retained HTTP timing p95 in milliseconds.",
        "# TYPE tquant_http_p95_ms gauge",
        f"tquant_http_p95_ms {snapshot.get('p95_ms', 0)}",
        "# HELP tquant_http_slow_requests Retained slow HTTP request count.",
        "# TYPE tquant_http_slow_requests gauge",
        f"tquant_http_slow_requests {snapshot.get('slow_count', 0)}",
        "# HELP tquant_agent_tool_calls_total Agent tool calls recorded in the audit log.",
        "# TYPE tquant_agent_tool_calls_total gauge",
        f"tquant_agent_tool_calls_total {agent_snapshot.get('calls_total', 0)}",
        "# HELP tquant_agent_tool_success_total Successful Agent tool calls recorded in the audit log.",
        "# TYPE tquant_agent_tool_success_total gauge",
        f"tquant_agent_tool_success_total {agent_snapshot.get('success_total', 0)}",
        "# HELP tquant_agent_tool_failure_total Failed Agent tool calls recorded in the audit log.",
        "# TYPE tquant_agent_tool_failure_total gauge",
        f"tquant_agent_tool_failure_total {agent_snapshot.get('failure_total', 0)}",
        "# HELP tquant_runtime_tasks_queued Queued runtime worker tasks.",
        "# TYPE tquant_runtime_tasks_queued gauge",
        f"tquant_runtime_tasks_queued {phase4_snapshot.get('runtime_tasks_queued', 0)}",
        "# HELP tquant_runtime_tasks_running Running runtime worker tasks.",
        "# TYPE tquant_runtime_tasks_running gauge",
        f"tquant_runtime_tasks_running {phase4_snapshot.get('runtime_tasks_running', 0)}",
        "# HELP tquant_runtime_tasks_failed Failed runtime worker tasks.",
        "# TYPE tquant_runtime_tasks_failed gauge",
        f"tquant_runtime_tasks_failed {phase4_snapshot.get('runtime_tasks_failed', 0)}",
        "# HELP tquant_agent_quality_blocked_total Agent quality results that failed validation.",
        "# TYPE tquant_agent_quality_blocked_total gauge",
        f"tquant_agent_quality_blocked_total {phase4_snapshot.get('agent_quality_blocked_total', 0)}",
    ]
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


@app.get("/", include_in_schema=False)
def root():
    if FRONTEND_INDEX_FILE.exists():
        return FileResponse(FRONTEND_INDEX_FILE)
    return HealthResponse(status="ok", app=settings.app_name)


@app.get("/backtests", include_in_schema=False)
def legacy_backtests_redirect(request: Request):
    return _legacy_route_response("/strategy?tab=backtest", request)


@app.get("/research", include_in_schema=False)
def legacy_research_redirect(request: Request):
    return _legacy_route_response("/strategy?tab=replay", request)


def _legacy_route_response(target: str, request: Request):
    accepts_html = "text/html" in request.headers.get("accept", "").lower()
    if settings.legacy_route_compat_enabled or accepts_html:
        status_code = 301 if settings.legacy_route_compat_enabled else 302
        return RedirectResponse(url=target, status_code=status_code)
    return JSONResponse(
        status_code=410,
        content={
            "code": "LEGACY_ROUTE_REMOVED",
            "message": "该旧入口已下线，请使用新的策略工作台入口。",
            "target": target,
        },
    )


@app.get("/{full_path:path}", include_in_schema=False)
def frontend_app(full_path: str):
    requested = FRONTEND_DIST_DIR / full_path
    try:
        resolved = requested.resolve()
        dist_root = FRONTEND_DIST_DIR.resolve()
    except OSError:
        resolved = None
        dist_root = FRONTEND_DIST_DIR.resolve()
    if resolved is not None and resolved.is_file() and dist_root in resolved.parents:
        return FileResponse(resolved)
    if FRONTEND_INDEX_FILE.exists():
        return FileResponse(FRONTEND_INDEX_FILE)
    return HealthResponse(status="ok", app=settings.app_name)
