from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime, time as dt_time
import logging
from pathlib import Path
import threading
import time

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import SessionLocal, init_db, ping_database
from app.core.logging_config import configure_logging
from app.core.rate_limit import is_global_rate_allowed
from app.core.task_manager import task_manager
from app.core.timing import record_request_timing
from app.models.schemas import HealthResponse, ReadinessResponse
from app.repositories.low_buy.results import LowBuyResultRepository
from app.services.low_buy.shared import DEFAULT_PRODUCTION_LOW_BUY_STRATEGY
from app.services.low_buy_screener import PLAYBOOKS, LowBuyScreenerService
from app.services.paper.archive import PaperArchiveService
from app.services.paper.scheduler import build_auto_trader_config, start_auto_trader, stop_auto_trader
from app.services.paper.validation_scheduler import MonthlyStrategyValidationJob
from app.services.auth_service import ensure_auth_secret_configured
from app.services.agent_signal_scan_service import AgentSignalScanService
from app.services.watchlist_signal_service import WatchlistSignalService

settings = get_settings()
configure_logging(structured=settings.structured_logs)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"
FRONTEND_INDEX_FILE = FRONTEND_DIST_DIR / "index.html"
FULL_SCAN_REFRESH_SECONDS = 60 * 60
WATCHLIST_REFRESH_SECONDS = 45
APP_LOW_BUY_STARTUP_LIMIT = 24
FULL_SCAN_BACKGROUND_LIMIT = 40
SQLITE_BACKGROUND_SCAN_LIMIT = 120
DEFAULT_BACKGROUND_SCAN_LIMIT = 480
logger = logging.getLogger(__name__)
_paper_archive_last_run_date: date | None = None


def _background_jobs_enabled() -> bool:
    if not settings.runtime_background_jobs_enabled:
        return False
    if settings.database_url.startswith("sqlite") and not settings.runtime_background_jobs_on_sqlite:
        return False
    return True


def _background_low_buy_strategies() -> list[str]:
    if settings.database_url.startswith("sqlite"):
        return [DEFAULT_PRODUCTION_LOW_BUY_STRATEGY]
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
    return not settings.database_url.startswith("sqlite")


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
    return (datetime.now() - updated_at).total_seconds() < max_age_seconds


def _warm_runtime_caches() -> None:
    db = SessionLocal()
    watchlist_signal_service = WatchlistSignalService()
    try:
        if _startup_low_buy_prewarm_enabled():
            _refresh_materialized_low_buy_snapshots(
                strategies=_background_low_buy_strategies(),
                limit=_background_low_buy_limit(),
                scan_limit=_background_low_buy_scan_limit(),
                compute_performance=not settings.database_url.startswith("sqlite"),
            )
        if _startup_low_buy_history_prewarm_enabled():
            screener = LowBuyScreenerService()
            screener.history(db=db, strategy=DEFAULT_PRODUCTION_LOW_BUY_STRATEGY)
        watchlist_signal_service.refresh_snapshots(force=True)
    except Exception:
        logger.exception("runtime cache prewarm failed")
    finally:
        db.close()


def _refresh_full_scan_once() -> None:
    _refresh_materialized_low_buy_snapshots(
        strategies=_background_low_buy_strategies(),
        limit=_background_low_buy_limit(),
        scan_limit=_background_low_buy_scan_limit(),
        compute_performance=not settings.database_url.startswith("sqlite"),
    )


def _refresh_watchlist_signal_once() -> None:
    watchlist_signal_service = WatchlistSignalService()
    watchlist_signal_service.refresh_snapshots(force=True)


def _archive_paper_performance_once() -> None:
    global _paper_archive_last_run_date
    if not _paper_archive_due():
        return
    today = date.today()
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


def _scan_priority_notifications_once() -> None:
    if not settings.notification_signal_scan_enabled:
        return
    if not settings.notification_feishu_webhook_url.strip():
        return
    with SessionLocal() as db:
        result = AgentSignalScanService().scan_priority_board(db, limit=12, channel="feishu")
        logger.info(
            "优先级榜通知扫描完成: scanned=%s sent=%s suppressed=%s upgraded=%s",
            result.scanned,
            result.sent,
            result.suppressed,
            result.upgraded,
        )


def _paper_archive_due() -> bool:
    try:
        hour, minute = [int(part) for part in settings.paper_perf_archive_time.split(":", 1)]
        archive_time = dt_time(hour=hour, minute=minute)
    except (TypeError, ValueError):
        logger.warning("PAPER_PERF_ARCHIVE_TIME 配置无效: %s", settings.paper_perf_archive_time)
        archive_time = dt_time(hour=15, minute=5)
    return datetime.now().time() >= archive_time


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_auth_secret_configured()
    init_db()
    if _background_jobs_enabled():
        threading.Thread(target=_warm_runtime_caches, daemon=True).start()
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
        if settings.notification_signal_scan_enabled:
            task_manager.register_loop(
                name="agent_priority_notifications",
                target=_scan_priority_notifications_once,
                interval_seconds=max(settings.notification_signal_scan_interval_seconds, 30),
                initial_delay_seconds=120,
            )
        if settings.paper_auto_trading_enabled:
            logger.info("启动模拟盘自动交易")
            start_auto_trader(build_auto_trader_config(settings))
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
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
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
                "slow_http_request method=%s path=%s status=%s duration_ms=%s",
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


@app.get("/", include_in_schema=False)
def root():
    if FRONTEND_INDEX_FILE.exists():
        return FileResponse(FRONTEND_INDEX_FILE)
    return HealthResponse(status="ok", app=settings.app_name)


@app.get("/{full_path:path}", include_in_schema=False)
def frontend_app(full_path: str):
    requested = FRONTEND_DIST_DIR / full_path
    if requested.is_file():
        return FileResponse(requested)
    if FRONTEND_INDEX_FILE.exists():
        return FileResponse(FRONTEND_INDEX_FILE)
    return HealthResponse(status="ok", app=settings.app_name)
