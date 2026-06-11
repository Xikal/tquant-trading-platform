from __future__ import annotations

from contextlib import asynccontextmanager
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from datetime import time as dt_time
import logging
import math
from pathlib import Path
import threading
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse

from app.agent_tools.audit import agent_audit_metrics
from app.api.router import api_router
from app.api.routes.strategy_stream import ws_router as strategy_ws_router
from app.core.admin_auth import require_admin_auth
from app.core.config import get_settings
from app.core.database import SessionLocal, init_db, ping_database
from app.core.logging_config import configure_logging
from app.core.rate_limit import is_global_rate_allowed
from app.core.security_config import validate_security_settings
from app.core.timing import record_request_timing, request_timing_snapshot
from app.core.timezone import beijing_now
from app.models.schemas import HealthResponse, ReadinessResponse
from app.runtime.background_jobs import shutdown_runtime_background_jobs, start_runtime_background_jobs
from app.services.auth_service import ensure_auth_secret_configured
from app.services.analytics.dependencies import analytics_dependency_status
from app.services.market.providers.circuit import provider_metrics_snapshot
from app.services.market.local_quote_cache import local_quote_cache_metrics_snapshot
from app.services.bff.workspace_cache import bff_workspace_cache_metrics_snapshot
from app.services.bff.remote_client import remote_bff_metrics_snapshot
from app.services.finance.rust_math import rust_math_metrics_snapshot
from app.services.operation_audit_middleware import OperationAuditMiddleware
from app.services.performance.prometheus import performance_prometheus_lines

settings = get_settings()
configure_logging(structured=settings.structured_logs)
logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_NEXT_DIST_DIR = PROJECT_ROOT / "frontend-next" / "dist"
FRONTEND_NEXT_INDEX_FILE = FRONTEND_NEXT_DIST_DIR / "index.html"
FRONTEND_NEXT_ROUTE_PREFIX = "next"
_INTERNAL_ERROR_MESSAGE = "服务内部错误，请稍后重试"
_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "style-src-elem 'self' 'unsafe-inline'; "
    "style-src-attr 'unsafe-inline'; "
    "img-src 'self' blob:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'"
)
_SECURITY_HEADERS = {
    "Content-Security-Policy": _CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
}
_SPA_INDEX_CACHE_CONTROL = "no-store, no-cache, must-revalidate, proxy-revalidate"
_READYZ_DB_TIMEOUT_SECONDS = 1.0
_READYZ_DB_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="readyz-db")
_readyz_db_probe_lock = threading.Lock()
_readyz_db_probe: Future[None] | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_auth_secret_configured()
    validate_security_settings(settings)
    init_db()
    start_runtime_background_jobs()
    try:
        yield
    finally:
        shutdown_runtime_background_jobs(timeout=30)


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Admin-Token", "X-Request-ID", "X-Requested-With", "traceparent"],
)
app.include_router(api_router, prefix=settings.api_prefix)
app.include_router(strategy_ws_router)
operation_audit_middleware = OperationAuditMiddleware()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", "") or request.headers.get("x-request-id") or f"req_{uuid4().hex}"
    logger.error(
        "unhandled_http_exception trace_id=%s method=%s path=%s",
        trace_id,
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    response = JSONResponse(
        status_code=500,
        content={"detail": _INTERNAL_ERROR_MESSAGE, "request_id": trace_id},
        headers={"X-Request-ID": trace_id, "traceparent": getattr(request.state, "traceparent", "") or _new_traceparent()},
    )
    _apply_security_headers(response, request)
    return response


@app.middleware("http")
async def enforce_internal_service_token(request, call_next):
    if _requires_internal_service_token(request):
        expected = settings.tquant_internal_service_token.strip()
        provided = request.headers.get("x-internal-service-token", "").strip()
        if not expected or provided != expected:
            response = JSONResponse(status_code=403, content={"detail": "内部服务认证失败"})
            _apply_security_headers(response, request)
            return response
    return await call_next(request)


@app.middleware("http")
async def enforce_request_body_limit(request, call_next):
    if not is_global_rate_allowed(request):
        response = JSONResponse(status_code=429, content={"detail": "请求过于频繁，请稍后再试。"})
        _apply_security_headers(response, request)
        return response
    if request.method in {"POST", "PUT", "PATCH"}:
        content_length = request.headers.get("content-length")
        if content_length and _content_length_exceeds_limit(content_length):
            response = JSONResponse(status_code=413, content={"detail": "请求体过大"})
            _apply_security_headers(response, request)
            return response
    return await call_next(request)


@app.middleware("http")
async def record_http_timing(request, call_next):
    trace_id = request.headers.get("x-request-id") or f"req_{uuid4().hex}"
    traceparent = request.headers.get("traceparent") or _new_traceparent()
    request.state.trace_id = trace_id
    request.state.traceparent = traceparent
    started = time.perf_counter()
    status_code = 500
    audit_candidate = operation_audit_middleware.candidate(request)
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = trace_id
        response.headers["traceparent"] = traceparent
        _apply_security_headers(response, request)
        return response
    finally:
        operation_audit_middleware.record(audit_candidate, status_code=status_code, path=request.url.path)
        duration_ms = int((time.perf_counter() - started) * 1000)
        record_request_timing(
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_ms=duration_ms,
        )
        if duration_ms >= 3000:
            logger.warning(
                "slow_http_request trace_id=%s traceparent=%s method=%s path=%s status=%s duration_ms=%s",
                trace_id,
                traceparent,
                request.method,
                request.url.path,
                status_code,
                duration_ms,
            )


def _apply_security_headers(response: Response, request: Request) -> None:
    for key, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(key, value)
    if _request_is_https(request):
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")


def _new_traceparent() -> str:
    value = uuid4().hex + uuid4().hex
    return f"00-{value[:32]}-{value[32:48]}-01"


def _request_is_https(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    return request.url.scheme == "https" or forwarded_proto == "https"


def _content_length_exceeds_limit(raw_value: str) -> bool:
    try:
        return int(raw_value) > settings.max_request_body_bytes
    except (TypeError, ValueError):
        return False


def _requires_internal_service_token(request: Request) -> bool:
    return bool(
        request.headers.get("x-tquant-bff-hop")
        or request.headers.get("x-internal-service-token")
    )


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
            completed_durations = [
                int((row.finished_at - row.started_at).total_seconds() * 1000)
                for row in db.execute(
                    select(RuntimeTask.started_at, RuntimeTask.finished_at)
                    .where(RuntimeTask.status == "succeeded")
                    .where(RuntimeTask.started_at.isnot(None))
                    .where(RuntimeTask.finished_at.isnot(None))
                    .order_by(RuntimeTask.finished_at.desc())
                    .limit(200)
                ).all()
                if row.started_at and row.finished_at and row.finished_at >= row.started_at
            ]
        return {
            "runtime_tasks_queued": queued,
            "runtime_tasks_running": running,
            "runtime_tasks_failed": failed,
            "runtime_task_duration_samples": len(completed_durations),
            "runtime_task_duration_p95_ms": _p95_int(completed_durations),
            "agent_quality_blocked_total": low_quality,
        }
    except Exception:
        logger.warning("phase4 metrics unavailable")
        return {
            "runtime_tasks_queued": 0,
            "runtime_tasks_running": 0,
            "runtime_tasks_failed": 0,
            "runtime_task_duration_samples": 0,
            "runtime_task_duration_p95_ms": 0,
            "agent_quality_blocked_total": 0,
        }


def _p95_int(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)
    return int(ordered[index])


def _provider_metrics_snapshot() -> dict[str, int]:
    snapshot = provider_metrics_snapshot()
    quote_cache = local_quote_cache_metrics_snapshot()
    return {
        "provider_calls_total": int(snapshot.get("provider_calls_total") or 0),
        "provider_success_total": int(snapshot.get("provider_success_total") or 0),
        "provider_failures_total": int(snapshot.get("provider_failures_total") or 0),
        "provider_slow_calls_total": int(snapshot.get("provider_slow_calls_total") or 0),
        "local_quote_cache_reads_total": int(quote_cache.get("reads") or 0),
        "local_quote_cache_hits_total": int(quote_cache.get("hits") or 0),
        "local_quote_cache_writes_total": int(quote_cache.get("writes") or 0),
        "local_quote_cache_misses_total": int(quote_cache.get("misses") or 0),
        "local_quote_cache_fresh_hits_total": int(quote_cache.get("fresh_hits") or 0),
        "local_quote_cache_stale_hits_total": int(quote_cache.get("stale_hits") or 0),
        "local_quote_cache_estimated_hits_total": int(quote_cache.get("estimated_hits") or 0),
        "local_quote_cache_coverage_checks_total": int(quote_cache.get("coverage_checks") or 0),
        "local_quote_cache_coverage_demand_total": int(quote_cache.get("coverage_demand_total") or 0),
        "local_quote_cache_coverage_demand_miss_total": int(quote_cache.get("coverage_demand_miss_total") or 0),
        "local_quote_cache_coverage_below_target_total": int(quote_cache.get("coverage_below_target_total") or 0),
        "local_quote_cache_coverage_ratio_bps": int(quote_cache.get("coverage_ratio_bps") or 0),
    }


def _market_close_review_due() -> bool:
    """Compatibility wrapper for tests and scripts that import main directly."""

    try:
        hour, minute = [int(part) for part in settings.market_close_review_time.split(":", 1)]
        review_time = dt_time(hour=hour, minute=minute)
    except (TypeError, ValueError):
        logger.warning("MARKET_CLOSE_REVIEW_TIME 配置无效: %s", settings.market_close_review_time)
        review_time = dt_time(hour=15, minute=5)
    return beijing_now().time() >= review_time


def _agent_daily_report_push_due() -> bool:
    """Compatibility wrapper for tests and scripts that import main directly."""

    now = beijing_now()
    if now.weekday() >= 5:
        return False
    return now.time() >= dt_time(hour=15, minute=10)


def _market_midday_review_due() -> bool:
    """Compatibility wrapper for tests and scripts that import main directly."""

    from app.runtime.market_review_jobs import market_midday_review_due

    return market_midday_review_due()


@app.get("/healthz", response_model=HealthResponse)
def healthz():
    return HealthResponse(status="ok", app=settings.app_name)


@app.get("/readyz", response_model=ReadinessResponse)
def readyz(response: Response):
    serve_frontend_static = bool(settings.serve_frontend_static)
    frontend_next_ready = (not serve_frontend_static) or FRONTEND_NEXT_INDEX_FILE.exists()
    checks = {
        "database": False,
        "frontend_next_dist": frontend_next_ready,
        # Compatibility alias for older probes. This now represents the active
        # frontend-next static entry rather than the retired legacy frontend.
        "frontend_dist": frontend_next_ready,
        "analytics_dependencies": False,
    }
    errors: list[str] = []

    database_ok, database_error = _ping_database_with_timeout(timeout_seconds=_READYZ_DB_TIMEOUT_SECONDS)
    checks["database"] = database_ok
    if not database_ok:
        errors.append(f"database: {database_error}")

    if serve_frontend_static and not checks["frontend_next_dist"]:
        errors.append("frontend_next_dist: missing frontend-next/dist/index.html")
    analytics = analytics_dependency_status()
    checks["analytics_dependencies"] = bool(analytics.ready or not analytics.enabled)
    if not checks["analytics_dependencies"]:
        errors.append(f"analytics_dependencies: {analytics.error}")

    if not all(checks.values()):
        response.status_code = 503
        return ReadinessResponse(
            status="degraded",
            app=settings.app_name,
            checks=checks,
            errors=errors,
        )

    return ReadinessResponse(status="ok", app=settings.app_name, checks=checks, errors=errors)


def _ping_database_with_timeout(*, timeout_seconds: float) -> tuple[bool, str]:
    global _readyz_db_probe
    effective_timeout = max(float(timeout_seconds), 0.05)
    with _readyz_db_probe_lock:
        if _readyz_db_probe is None or _readyz_db_probe.done():
            _readyz_db_probe = _READYZ_DB_EXECUTOR.submit(ping_database)
        future = _readyz_db_probe
    try:
        future.result(timeout=effective_timeout)
        return True, ""
    except TimeoutError:
        return False, f"timeout_after_{effective_timeout:.2f}s"
    except Exception as exc:
        with _readyz_db_probe_lock:
            if future is _readyz_db_probe:
                _readyz_db_probe = None
        return False, str(exc)


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics(_: None = Depends(require_admin_auth)) -> PlainTextResponse:
    snapshot = request_timing_snapshot()
    agent_snapshot = _agent_audit_metrics_snapshot()
    phase4_snapshot = _phase4_metrics_snapshot()
    provider_snapshot = _provider_metrics_snapshot()
    bff_cache_snapshot = bff_workspace_cache_metrics_snapshot()
    bff_remote_snapshot = remote_bff_metrics_snapshot()
    rust_snapshot = rust_math_metrics_snapshot()
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
        "# HELP tquant_runtime_task_duration_samples Retained completed runtime worker task duration samples.",
        "# TYPE tquant_runtime_task_duration_samples gauge",
        f"tquant_runtime_task_duration_samples {phase4_snapshot.get('runtime_task_duration_samples', 0)}",
        "# HELP tquant_runtime_task_duration_p95_ms Completed runtime worker task duration p95 in milliseconds.",
        "# TYPE tquant_runtime_task_duration_p95_ms gauge",
        f"tquant_runtime_task_duration_p95_ms {phase4_snapshot.get('runtime_task_duration_p95_ms', 0)}",
        "# HELP tquant_agent_quality_blocked_total Agent quality results that failed validation.",
        "# TYPE tquant_agent_quality_blocked_total gauge",
        f"tquant_agent_quality_blocked_total {phase4_snapshot.get('agent_quality_blocked_total', 0)}",
        "# HELP tquant_bff_workspace_cache_reads_total BFF workspace cache read attempts.",
        "# TYPE tquant_bff_workspace_cache_reads_total counter",
        f"tquant_bff_workspace_cache_reads_total {bff_cache_snapshot.get('reads', 0)}",
        "# HELP tquant_bff_workspace_cache_hits_total BFF workspace cache hits.",
        "# TYPE tquant_bff_workspace_cache_hits_total counter",
        f"tquant_bff_workspace_cache_hits_total {bff_cache_snapshot.get('hits', 0)}",
        "# HELP tquant_bff_workspace_cache_writes_total BFF workspace cache writes.",
        "# TYPE tquant_bff_workspace_cache_writes_total counter",
        f"tquant_bff_workspace_cache_writes_total {bff_cache_snapshot.get('writes', 0)}",
        "# HELP tquant_bff_workspace_cache_skips_total BFF workspace cache skipped loads.",
        "# TYPE tquant_bff_workspace_cache_skips_total counter",
        f"tquant_bff_workspace_cache_skips_total {bff_cache_snapshot.get('skips', 0)}",
        "# HELP tquant_bff_workspace_cache_schema_misses_total BFF workspace cache schema mismatches.",
        "# TYPE tquant_bff_workspace_cache_schema_misses_total counter",
        f"tquant_bff_workspace_cache_schema_misses_total {bff_cache_snapshot.get('schema_misses', 0)}",
        "# HELP tquant_bff_remote_calls_total BFF remote adapter call attempts.",
        "# TYPE tquant_bff_remote_calls_total counter",
        f"tquant_bff_remote_calls_total {bff_remote_snapshot.get('calls', 0)}",
        "# HELP tquant_bff_remote_success_total BFF remote adapter successful calls.",
        "# TYPE tquant_bff_remote_success_total counter",
        f"tquant_bff_remote_success_total {bff_remote_snapshot.get('successes', 0)}",
        "# HELP tquant_bff_remote_failures_total BFF remote adapter failed calls.",
        "# TYPE tquant_bff_remote_failures_total counter",
        f"tquant_bff_remote_failures_total {bff_remote_snapshot.get('failures', 0)}",
        "# HELP tquant_bff_remote_circuit_short_circuits_total BFF remote calls skipped by open circuit.",
        "# TYPE tquant_bff_remote_circuit_short_circuits_total counter",
        f"tquant_bff_remote_circuit_short_circuits_total {bff_remote_snapshot.get('circuit_short_circuits', 0)}",
        "# HELP tquant_bff_remote_credentials_suppressed_total BFF remote calls with credentials suppressed for untrusted targets.",
        "# TYPE tquant_bff_remote_credentials_suppressed_total counter",
        f"tquant_bff_remote_credentials_suppressed_total {bff_remote_snapshot.get('credentials_suppressed', 0)}",
        "# HELP tquant_rust_math_hits_total Rust finance math successful calls.",
        "# TYPE tquant_rust_math_hits_total counter",
        f"tquant_rust_math_hits_total {rust_snapshot.get('hits', 0)}",
        "# HELP tquant_rust_math_fallbacks_total Rust finance math module fallback calls.",
        "# TYPE tquant_rust_math_fallbacks_total counter",
        f"tquant_rust_math_fallbacks_total {rust_snapshot.get('fallbacks', 0)}",
        "# HELP tquant_rust_math_errors_total Rust finance math execution errors.",
        "# TYPE tquant_rust_math_errors_total counter",
        f"tquant_rust_math_errors_total {rust_snapshot.get('errors', 0)}",
        "# HELP tquant_rust_math_disabled_total Rust finance math disabled checks.",
        "# TYPE tquant_rust_math_disabled_total counter",
        f"tquant_rust_math_disabled_total {rust_snapshot.get('disabled', 0)}",
        "# HELP tquant_rust_math_fallback_ratio_bps Rust finance math fallback ratio in basis points.",
        "# TYPE tquant_rust_math_fallback_ratio_bps gauge",
        f"tquant_rust_math_fallback_ratio_bps {rust_snapshot.get('fallback_ratio_bps', 0)}",
        "# HELP tquant_derived_indicator_cache_hits_total Derived finance indicator cache hits.",
        "# TYPE tquant_derived_indicator_cache_hits_total counter",
        f"tquant_derived_indicator_cache_hits_total {rust_snapshot.get('cache_hits', 0)}",
        "# HELP tquant_derived_indicator_cache_misses_total Derived finance indicator cache misses.",
        "# TYPE tquant_derived_indicator_cache_misses_total counter",
        f"tquant_derived_indicator_cache_misses_total {rust_snapshot.get('cache_misses', 0)}",
        "# HELP tquant_derived_indicator_cache_size Derived finance indicator cache size.",
        "# TYPE tquant_derived_indicator_cache_size gauge",
        f"tquant_derived_indicator_cache_size {rust_snapshot.get('cache_size', 0)}",
        "# HELP tquant_provider_calls_total Market provider calls across configured providers.",
        "# TYPE tquant_provider_calls_total counter",
        f"tquant_provider_calls_total {provider_snapshot.get('provider_calls_total', 0)}",
        "# HELP tquant_provider_failures_total Failed market provider calls.",
        "# TYPE tquant_provider_failures_total counter",
        f"tquant_provider_failures_total {provider_snapshot.get('provider_failures_total', 0)}",
        "# HELP tquant_provider_slow_calls_total Slow market provider calls.",
        "# TYPE tquant_provider_slow_calls_total counter",
        f"tquant_provider_slow_calls_total {provider_snapshot.get('provider_slow_calls_total', 0)}",
        "# HELP tquant_local_quote_cache_reads_total Local quote cache reads.",
        "# TYPE tquant_local_quote_cache_reads_total counter",
        f"tquant_local_quote_cache_reads_total {provider_snapshot.get('local_quote_cache_reads_total', 0)}",
        "# HELP tquant_local_quote_cache_hits_total Local quote cache hits.",
        "# TYPE tquant_local_quote_cache_hits_total counter",
        f"tquant_local_quote_cache_hits_total {provider_snapshot.get('local_quote_cache_hits_total', 0)}",
        "# HELP tquant_local_quote_cache_writes_total Local quote cache writes.",
        "# TYPE tquant_local_quote_cache_writes_total counter",
        f"tquant_local_quote_cache_writes_total {provider_snapshot.get('local_quote_cache_writes_total', 0)}",
        "# HELP tquant_local_quote_cache_misses_total Local quote cache misses.",
        "# TYPE tquant_local_quote_cache_misses_total counter",
        f"tquant_local_quote_cache_misses_total {provider_snapshot.get('local_quote_cache_misses_total', 0)}",
        "# HELP tquant_local_quote_cache_fresh_hits_total Fresh local quote cache hits.",
        "# TYPE tquant_local_quote_cache_fresh_hits_total counter",
        f"tquant_local_quote_cache_fresh_hits_total {provider_snapshot.get('local_quote_cache_fresh_hits_total', 0)}",
        "# HELP tquant_local_quote_cache_stale_hits_total Stale local quote cache hits.",
        "# TYPE tquant_local_quote_cache_stale_hits_total counter",
        f"tquant_local_quote_cache_stale_hits_total {provider_snapshot.get('local_quote_cache_stale_hits_total', 0)}",
        "# HELP tquant_local_quote_cache_estimated_hits_total Estimated local quote cache hits.",
        "# TYPE tquant_local_quote_cache_estimated_hits_total counter",
        f"tquant_local_quote_cache_estimated_hits_total {provider_snapshot.get('local_quote_cache_estimated_hits_total', 0)}",
        "# HELP tquant_local_quote_cache_coverage_checks_total Local quote cache hot-demand coverage checks.",
        "# TYPE tquant_local_quote_cache_coverage_checks_total counter",
        f"tquant_local_quote_cache_coverage_checks_total {provider_snapshot.get('local_quote_cache_coverage_checks_total', 0)}",
        "# HELP tquant_local_quote_cache_coverage_demand_total Symbols included in quote cache hot-demand coverage checks.",
        "# TYPE tquant_local_quote_cache_coverage_demand_total counter",
        f"tquant_local_quote_cache_coverage_demand_total {provider_snapshot.get('local_quote_cache_coverage_demand_total', 0)}",
        "# HELP tquant_local_quote_cache_coverage_demand_miss_total Symbols missing from quote cache hot-demand coverage checks.",
        "# TYPE tquant_local_quote_cache_coverage_demand_miss_total counter",
        f"tquant_local_quote_cache_coverage_demand_miss_total {provider_snapshot.get('local_quote_cache_coverage_demand_miss_total', 0)}",
        "# HELP tquant_local_quote_cache_coverage_below_target_total Quote cache coverage checks below target.",
        "# TYPE tquant_local_quote_cache_coverage_below_target_total counter",
        f"tquant_local_quote_cache_coverage_below_target_total {provider_snapshot.get('local_quote_cache_coverage_below_target_total', 0)}",
        "# HELP tquant_local_quote_cache_coverage_ratio_bps Last hot-demand quote cache coverage ratio in basis points.",
        "# TYPE tquant_local_quote_cache_coverage_ratio_bps gauge",
        f"tquant_local_quote_cache_coverage_ratio_bps {provider_snapshot.get('local_quote_cache_coverage_ratio_bps', 0)}",
    ]
    lines.extend(performance_prometheus_lines())
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


@app.get("/", include_in_schema=False)
def root():
    if not settings.serve_frontend_static:
        return HealthResponse(status="ok", app=settings.app_name)
    return _serve_frontend_next("/")


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


def _serve_frontend_dist(dist_dir: Path, index_file: Path, full_path: str) -> FileResponse | HealthResponse | JSONResponse:
    requested = dist_dir / full_path
    try:
        resolved = requested.resolve()
        dist_root = dist_dir.resolve()
    except OSError:
        resolved = None
        dist_root = dist_dir.resolve()
    if resolved is not None and resolved.is_file() and dist_root in resolved.parents:
        return _frontend_file_response(resolved, is_index=resolved.name == "index.html")
    if _is_frontend_asset_request(full_path):
        return JSONResponse(status_code=404, content={"detail": "Frontend asset not found"})
    if index_file.exists():
        return _frontend_file_response(index_file, is_index=True)
    return HealthResponse(status="ok", app=settings.app_name)


def _is_frontend_asset_request(full_path: str) -> bool:
    normalized = full_path.strip("/")
    return normalized.startswith("assets/") or Path(normalized).suffix != ""


def _frontend_file_response(path: Path, *, is_index: bool) -> FileResponse:
    headers = {"Cache-Control": _SPA_INDEX_CACHE_CONTROL} if is_index else None
    return FileResponse(path, headers=headers)


def _serve_frontend_next(full_path: str) -> FileResponse | HealthResponse | JSONResponse:
    normalized = full_path.strip("/")
    if normalized == FRONTEND_NEXT_ROUTE_PREFIX:
        relative_path = ""
    elif normalized.startswith(f"{FRONTEND_NEXT_ROUTE_PREFIX}/"):
        relative_path = normalized[len(FRONTEND_NEXT_ROUTE_PREFIX) + 1 :]
    else:
        relative_path = normalized
    return _serve_frontend_dist(FRONTEND_NEXT_DIST_DIR, FRONTEND_NEXT_INDEX_FILE, relative_path)


@app.get("/{full_path:path}", include_in_schema=False)
def frontend_app(full_path: str):
    api_prefix = settings.api_prefix.strip("/")
    if full_path == api_prefix or full_path.startswith(f"{api_prefix}/"):
        return JSONResponse(status_code=404, content={"detail": "API endpoint not found"})
    if not settings.serve_frontend_static:
        return JSONResponse(status_code=404, content={"detail": "Frontend static serving is disabled"})
    if full_path.strip("/").startswith("__legacy/"):
        return JSONResponse(status_code=404, content={"detail": "Legacy frontend assets have been retired"})
    return _serve_frontend_next(full_path)
