from __future__ import annotations

import logging
from typing import Callable, TypeVar

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request
from sqlalchemy import inspect as sa_inspect, select
from sqlalchemy.orm import Session

from app.api.routes.market import _enqueue_market_pulse_refresh, market_breadth, paired_hedge_research, sector_relative_strength
from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.database import SessionLocal, get_db
from app.core.paper_auth import require_paper_trading
from app.core.admin_auth import require_admin_auth
from app.core.role_permissions import is_admin_user
from app.core.timezone import beijing_now_string, beijing_today
from app.models.entities import User
from app.models.schema_defs.bff import (
    BFF_SCHEMA_VERSION,
    BffManifestResponse,
    BffWorkspaceManifest,
    BffPartialError,
    MonitorWorkspaceBffResponse,
    PaperWorkspaceBffResponse,
    SettingsWorkspaceBffResponse,
    StrategyWorkspaceBffResponse,
)
from app.services.bff.paper_workspace import build_paper_workspace
from app.services.bff.remote_adapters import (
    load_remote_monitor_workspace,
    load_remote_paper_workspace,
    load_remote_settings_workspace,
    load_remote_strategy_workspace,
)
from app.services.bff.remote_client import forwarded_request_headers
from app.services.bff.go_gateway_shadow import schedule_go_bff_shadow_check
from app.services.bff.settings_workspace import build_settings_workspace
from app.services.bff.strategy_workspace import build_strategy_workspace
from app.services.bff.timeout import run_workspace_with_timeout
from app.services.bff.workspace_cache import load_cached_workspace
from app.services.market.pulse_cache import latest_pulse_or_placeholder
from app.services.market.pulse_history import list_hourly_snapshot_history
from app.services.monitor_snapshot_service import build_monitor_snapshot
from app.services.market.review import build_market_review_summary
from app.services.performance.read_model_metrics import record_bff_partial_failure, record_response_payload
from app.services.read_models.live_quote_overlay import apply_monitor_workspace_live_overlay
from app.services.settings_runtime import SettingsRuntimeDiagnosticsService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bff/v1", dependencies=[Depends(get_current_user)])
T = TypeVar("T")
NONCRITICAL_MONITOR_SOURCES = {
    "review",
    "hourly_snapshot_history",
    "extended_diagnostics",
}
CRITICAL_MONITOR_SOURCES = {
    "monitor_snapshot",
    "market_breadth",
    "market_pulse",
    "sector_relative_strength",
    "paired_hedge",
    "runtime",
}
MONITOR_SOURCE_TIMEOUT_MS = {
    "review": 80,
    "hourly_snapshot_history": 80,
    "extended_diagnostics": 120,
}


@router.get("/manifest", response_model=BffManifestResponse)
def bff_manifest(request: Request, background_tasks: BackgroundTasks) -> BffManifestResponse:
    """Expose the stable BFF contract consumed by Web/App frontends."""

    response = BffManifestResponse(
        modules=[
            "auth",
            "market",
            "strategy",
            "trade",
            "factor",
            "monitor",
            "settings",
        ],
        workspaces={
            "monitor": BffWorkspaceManifest(
                path="/api/bff/v1/workspace/monitor",
                schema_version=BFF_SCHEMA_VERSION,
                model="MonitorWorkspaceBffResponse",
            ),
            "paper": BffWorkspaceManifest(
                path="/api/bff/v1/workspace/paper",
                schema_version=BFF_SCHEMA_VERSION,
                model="PaperWorkspaceBffResponse",
            ),
            "strategy": BffWorkspaceManifest(
                path="/api/bff/v1/workspace/strategy",
                schema_version=BFF_SCHEMA_VERSION,
                model="StrategyWorkspaceBffResponse",
            ),
            "settings": BffWorkspaceManifest(
                path="/api/bff/v1/workspace/settings",
                schema_version=BFF_SCHEMA_VERSION,
                model="SettingsWorkspaceBffResponse",
            ),
        },
    )
    schedule_go_bff_shadow_check(
        background_tasks,
        workspace="manifest",
        response_model=BffManifestResponse,
        local_payload=response,
        request_headers=forwarded_request_headers(request.headers),
    )
    return response


@router.get("/workspace/monitor", response_model=MonitorWorkspaceBffResponse)
def monitor_workspace_bff(
    request: Request,
    background_tasks: BackgroundTasks,
    priority_limit: int = Query(default=12, ge=1, le=30),
    sector_limit: int = Query(default=8, ge=1, le=20),
    per_sector_limit: int = Query(default=8, ge=1, le=30),
    hedge_limit: int = Query(default=4, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MonitorWorkspaceBffResponse:
    """Aggregate monitor first-screen data behind a frontend-specific seam."""

    if not getattr(get_settings(), "monitor_bff_aggregate_enabled", True):
        raise HTTPException(status_code=404, detail="monitor BFF aggregate disabled")

    include_runtime = _monitor_runtime_allowed(request, current_user)
    remote_used = False
    if _remote_adapter_allowed(request):
        remote = load_remote_monitor_workspace(
            priority_limit=priority_limit,
            sector_limit=sector_limit,
            per_sector_limit=per_sector_limit,
            hedge_limit=hedge_limit,
            forward_headers=forwarded_request_headers(request.headers),
        )
        if remote is not None:
            remote_used = True
            response = apply_monitor_workspace_live_overlay(remote)
            _record_partial_errors(response)
            record_response_payload("monitor_bff", response, item_count=_monitor_priority_item_count(response))
            schedule_go_bff_shadow_check(
                background_tasks,
                workspace="monitor",
                response_model=MonitorWorkspaceBffResponse,
                local_payload=response,
                request_headers=forwarded_request_headers(request.headers),
                params={
                    "priority_limit": priority_limit,
                    "sector_limit": sector_limit,
                    "per_sector_limit": per_sector_limit,
                    "hedge_limit": hedge_limit,
                },
            )
            return response

    response = load_cached_workspace(
        workspace="monitor",
        model=MonitorWorkspaceBffResponse,
        user_id=current_user.id,
        params={
            "priority_limit": priority_limit,
            "sector_limit": sector_limit,
            "per_sector_limit": per_sector_limit,
            "hedge_limit": hedge_limit,
            "include_runtime": include_runtime,
        },
        loader=lambda: _build_monitor_workspace(
            db,
            current_user=current_user,
            priority_limit=priority_limit,
            sector_limit=sector_limit,
            per_sector_limit=per_sector_limit,
            hedge_limit=hedge_limit,
            allow_live_sources=False,
            include_runtime=include_runtime,
        ),
    )
    response = apply_monitor_workspace_live_overlay(response)
    _record_partial_errors(response)
    record_response_payload("monitor_bff", response, item_count=_monitor_priority_item_count(response))
    if not remote_used:
        schedule_go_bff_shadow_check(
            background_tasks,
            workspace="monitor",
            response_model=MonitorWorkspaceBffResponse,
            local_payload=response,
            request_headers=forwarded_request_headers(request.headers),
            params={
                "priority_limit": priority_limit,
                "sector_limit": sector_limit,
                "per_sector_limit": per_sector_limit,
                "hedge_limit": hedge_limit,
            },
        )
    return response


@router.get("/workspace/paper", response_model=PaperWorkspaceBffResponse)
def paper_workspace_bff(
    request: Request,
    background_tasks: BackgroundTasks,
    order_limit: int = Query(default=80, ge=1, le=200),
    trade_limit: int = Query(default=300, ge=1, le=300),
    run_limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperWorkspaceBffResponse:
    """Aggregate the paper trading first-screen payload for Web/App clients."""

    remote_used = False
    if _remote_adapter_allowed(request):
        remote = load_remote_paper_workspace(
            order_limit=order_limit,
            trade_limit=trade_limit,
            run_limit=run_limit,
            forward_headers=forwarded_request_headers(request.headers),
        )
        if remote is not None:
            remote_used = True
            response = remote
            _record_partial_errors(response)
            schedule_go_bff_shadow_check(
                background_tasks,
                workspace="paper",
                response_model=PaperWorkspaceBffResponse,
                local_payload=response,
                request_headers=forwarded_request_headers(request.headers),
                params={"order_limit": order_limit, "trade_limit": trade_limit, "run_limit": run_limit},
            )
            return response

    response = load_cached_workspace(
        workspace="paper",
        model=PaperWorkspaceBffResponse,
        user_id=current_user.id,
        params={"order_limit": order_limit, "trade_limit": trade_limit, "run_limit": run_limit},
        loader=lambda: run_workspace_with_timeout(
            source="paper_workspace",
            timeout_seconds=_bff_timeout_seconds(),
            loader=lambda: build_paper_workspace(
                db,
                current_user=current_user,
                order_limit=order_limit,
                trade_limit=trade_limit,
                run_limit=run_limit,
            ),
            fallback=lambda error: PaperWorkspaceBffResponse(
                generated_at=beijing_now_string(),
                partial_errors=[error],
            ),
        ),
    )
    _record_partial_errors(response)
    if not remote_used:
        schedule_go_bff_shadow_check(
            background_tasks,
            workspace="paper",
            response_model=PaperWorkspaceBffResponse,
            local_payload=response,
            request_headers=forwarded_request_headers(request.headers),
            params={"order_limit": order_limit, "trade_limit": trade_limit, "run_limit": run_limit},
        )
    return response


@router.get("/workspace/strategy", response_model=StrategyWorkspaceBffResponse)
def strategy_workspace_bff(
    request: Request,
    background_tasks: BackgroundTasks,
    run_limit: int = Query(default=8, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StrategyWorkspaceBffResponse:
    """Aggregate StrategyHub first-screen data for Web/App clients."""

    remote_used = False
    if _remote_adapter_allowed(request):
        remote = load_remote_strategy_workspace(
            run_limit=run_limit,
            forward_headers=forwarded_request_headers(request.headers),
        )
        if remote is not None:
            remote_used = True
            response = remote
            _record_partial_errors(response)
            schedule_go_bff_shadow_check(
                background_tasks,
                workspace="strategy",
                response_model=StrategyWorkspaceBffResponse,
                local_payload=response,
                request_headers=forwarded_request_headers(request.headers),
                params={"run_limit": run_limit},
            )
            return response

    response = load_cached_workspace(
        workspace="strategy",
        model=StrategyWorkspaceBffResponse,
        user_id=current_user.id,
        params={"run_limit": run_limit},
        loader=lambda: run_workspace_with_timeout(
            source="strategy_workspace",
            timeout_seconds=_bff_timeout_seconds(),
            loader=lambda: build_strategy_workspace(db, current_user=current_user, run_limit=run_limit),
            fallback=lambda error: StrategyWorkspaceBffResponse(
                generated_at=beijing_now_string(),
                partial_errors=[error],
            ),
        ),
    )
    _record_partial_errors(response)
    if not remote_used:
        schedule_go_bff_shadow_check(
            background_tasks,
            workspace="strategy",
            response_model=StrategyWorkspaceBffResponse,
            local_payload=response,
            request_headers=forwarded_request_headers(request.headers),
            params={"run_limit": run_limit},
        )
    return response


@router.get("/workspace/settings", response_model=SettingsWorkspaceBffResponse)
def settings_workspace_bff(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    authorization: str | None = Header(default=None),
) -> SettingsWorkspaceBffResponse:
    """Aggregate Settings page data while keeping admin-only sections gated."""

    include_admin = _settings_admin_enabled(
        request=request,
        current_user=current_user,
        x_admin_token=x_admin_token,
        authorization=authorization,
    )
    remote_used = False
    if _remote_adapter_allowed(request):
        remote = load_remote_settings_workspace(
            include_admin=include_admin,
            forward_headers=forwarded_request_headers(request.headers),
        )
        if remote is not None:
            remote_used = True
            response = remote
            _record_partial_errors(response)
            schedule_go_bff_shadow_check(
                background_tasks,
                workspace="settings",
                response_model=SettingsWorkspaceBffResponse,
                local_payload=response,
                request_headers=forwarded_request_headers(request.headers),
                params={"include_admin": str(include_admin).lower()},
            )
            return response

    response = load_cached_workspace(
        workspace="settings",
        model=SettingsWorkspaceBffResponse,
        user_id=current_user.id,
        params={"include_admin": include_admin},
        loader=lambda: run_workspace_with_timeout(
            source="settings_workspace",
            timeout_seconds=_bff_timeout_seconds(),
            loader=lambda: build_settings_workspace(
                db,
                current_user=current_user,
                include_admin=include_admin,
            ),
            fallback=lambda error: SettingsWorkspaceBffResponse(
                generated_at=beijing_now_string(),
                admin_enabled=include_admin,
                partial_errors=[error],
            ),
        ),
    )
    _record_partial_errors(response)
    if not remote_used:
        schedule_go_bff_shadow_check(
            background_tasks,
            workspace="settings",
            response_model=SettingsWorkspaceBffResponse,
            local_payload=response,
            request_headers=forwarded_request_headers(request.headers),
            params={"include_admin": str(include_admin).lower()},
        )
    return response


def _build_monitor_workspace(
    db: Session,
    *,
    current_user: User,
    priority_limit: int,
    sector_limit: int,
    per_sector_limit: int,
    hedge_limit: int,
    allow_live_sources: bool = True,
    include_runtime: bool = False,
) -> MonitorWorkspaceBffResponse:
    errors: list[BffPartialError] = []
    monitor_snapshot_payload = _safe(
        "monitor_snapshot",
        errors,
        lambda: build_monitor_snapshot(db, current_user=current_user, priority_limit=priority_limit),
    )
    market_breadth_payload = None
    sector_payload = None
    paired_payload = None
    if allow_live_sources:
        market_breadth_payload = _safe("market_breadth", errors, lambda: market_breadth(realtime=False, db=db))
        sector_payload = _safe(
            "sector_relative_strength",
            errors,
            lambda: sector_relative_strength(sector_limit, per_sector_limit, db),
        )
        paired_payload = _safe(
            "paired_hedge",
            errors,
            lambda: paired_hedge_research(hedge_limit, _attached_user(db, current_user), db),
            ignore_forbidden=True,
        )
    threaded_db_budget = _monitor_db_source_thread_budget_allowed(db)
    review_status, review_reports = _safe_monitor_source(
        "review",
        errors,
        lambda: _run_monitor_db_source(db, lambda source_db: build_market_review_summary(source_db)),
        default=(None, []),
        threaded=threaded_db_budget,
    ) or (None, [])
    hourly_history = _safe_monitor_source(
        "hourly_snapshot_history",
        errors,
        lambda: _run_monitor_db_source(db, _safe_hourly_snapshot_history),
        default=[],
        threaded=threaded_db_budget,
    ) or []
    pulse = _safe_market_pulse_snapshot(db, errors)
    runtime = _safe_runtime_status(db, current_user, errors) if include_runtime else None
    return MonitorWorkspaceBffResponse(
        generated_at=beijing_now_string(),
        monitor_snapshot=monitor_snapshot_payload,
        market_breadth=market_breadth_payload,
        sector_relative_strength=sector_payload,
        market_pulse=pulse,
        hourly_snapshot_history=hourly_history,
        review_status=review_status,
        review_reports=review_reports,
        paired_hedge=paired_payload,
        runtime=runtime,
        partial_errors=errors,
    )


def _safe_market_pulse_snapshot(db: Session, errors: list[BffPartialError]):
    try:
        pulse, pulse_needs_refresh = latest_pulse_or_placeholder(db, trade_date=beijing_today().isoformat())
    except Exception as exc:
        logger.warning("bff source failed source=market_pulse", exc_info=(type(exc), exc, exc.__traceback__))
        errors.append(
            BffPartialError(
                source="market_pulse",
                detail="盘中 pulse 快照暂时不可用",
                reason="other",
                fallback_source="python_local",
                message="market pulse snapshot unavailable",
            )
        )
        return None
    if pulse_needs_refresh:
        _enqueue_market_pulse_refresh(db, reason="bff_monitor_workspace")
    return pulse


def _safe_hourly_snapshot_history(db: Session):
    if not hasattr(db, "execute"):
        return []
    return list_hourly_snapshot_history(db, trade_date="", limit=8)


def _safe_runtime_status(db: Session, current_user: User, errors: list[BffPartialError]):
    try:
        if not is_admin_user(current_user):
            return None
    except Exception:
        return None
    try:
        return SettingsRuntimeDiagnosticsService(db).build_status()
    except Exception as exc:
        logger.warning("bff source failed source=runtime", exc_info=(type(exc), exc, exc.__traceback__))
        errors.append(
            BffPartialError(
                source="runtime",
                detail="运行态诊断暂时不可用",
                reason="other",
                fallback_source="python_local",
                message="runtime status unavailable",
            )
        )
        return None


def _monitor_runtime_allowed(request: Request, current_user: User) -> bool:
    try:
        if is_admin_user(current_user):
            return True
    except Exception:
        pass
    try:
        require_admin_auth(
            request,
            x_admin_token=request.headers.get("X-Admin-Token"),
            authorization=request.headers.get("Authorization"),
        )
        return True
    except HTTPException:
        return False
    except Exception:
        return False


def _safe(
    source: str,
    errors: list[BffPartialError],
    loader: Callable[[], T],
    *,
    ignore_forbidden: bool = False,
) -> T | None:
    try:
        return loader()
    except HTTPException as exc:
        if ignore_forbidden and exc.status_code == 403:
            return None
        errors.append(
            BffPartialError(
                source=source,
                detail=str(exc.detail),
                reason="status",
                status_code=exc.status_code,
                fallback_source="python_local",
                message="source returned HTTPException",
            )
        )
        return None
    except Exception as exc:
        logger.warning("bff source failed source=%s", source, exc_info=(type(exc), exc, exc.__traceback__))
        errors.append(
            BffPartialError(
                source=source,
                detail="数据暂时不可用",
                reason="other",
                fallback_source="python_local",
                message="source unavailable",
            )
        )
        return None


def _safe_monitor_source(
    source: str,
    errors: list[BffPartialError],
    loader: Callable[[], T],
    *,
    default: T,
    timeout_ms: int | None = None,
    threaded: bool = True,
) -> T:
    if not getattr(get_settings(), "monitor_bff_source_budget_enabled", True):
        result = _safe(source, errors, loader)
        return result if result is not None else default
    effective_timeout_ms = timeout_ms or MONITOR_SOURCE_TIMEOUT_MS.get(source)
    if effective_timeout_ms and effective_timeout_ms > 0 and threaded:
        try:
            return run_workspace_with_timeout(
                source=source,
                timeout_seconds=float(effective_timeout_ms) / 1000.0,
                loader=loader,
                fallback=lambda error: _record_monitor_timeout_fallback(
                    source,
                    errors,
                    default,
                    timeout_ms=error.timeout_ms or effective_timeout_ms,
                    message=error.message or error.detail,
                ),
            )
        except TimeoutError as exc:
            errors.append(_partial_error(source, "timeout", str(exc), timeout_ms=effective_timeout_ms))
            return default
        except HTTPException as exc:
            if source in NONCRITICAL_MONITOR_SOURCES:
                errors.append(_partial_error(source, "status", str(exc.detail), timeout_ms=effective_timeout_ms, status_code=exc.status_code))
                return default
            errors.append(_partial_error(source, "status", str(exc.detail), timeout_ms=effective_timeout_ms, status_code=exc.status_code))
            return default
        except Exception as exc:
            logger.warning("bff source failed source=%s", source, exc_info=(type(exc), exc, exc.__traceback__))
            errors.append(_partial_error(source, "error", str(exc), timeout_ms=effective_timeout_ms))
            return default
    try:
        return loader()
    except HTTPException as exc:
        if source in NONCRITICAL_MONITOR_SOURCES:
            errors.append(_partial_error(source, "status", str(exc.detail), timeout_ms=timeout_ms, status_code=exc.status_code))
            return default
        errors.append(_partial_error(source, "status", str(exc.detail), timeout_ms=timeout_ms, status_code=exc.status_code))
        return default
    except TimeoutError as exc:
        errors.append(_partial_error(source, "timeout", str(exc), timeout_ms=timeout_ms or MONITOR_SOURCE_TIMEOUT_MS.get(source)))
        return default
    except Exception as exc:
        logger.warning("bff source failed source=%s", source, exc_info=(type(exc), exc, exc.__traceback__))
        errors.append(_partial_error(source, "error", str(exc), timeout_ms=timeout_ms or MONITOR_SOURCE_TIMEOUT_MS.get(source)))
        return default


def _run_monitor_db_source(db: Session, loader: Callable[[Session], T]) -> T:
    if not _monitor_db_source_thread_budget_allowed(db):
        return loader(db)
    with SessionLocal() as source_db:
        return loader(source_db)


def _monitor_db_source_thread_budget_allowed(db: Session) -> bool:
    try:
        bind = db.get_bind()
        url = str(bind.url)
    except Exception:
        return False
    return url not in {"sqlite:///:memory:", "sqlite://"}


def _record_monitor_timeout_fallback(
    source: str,
    errors: list[BffPartialError],
    default: T,
    *,
    timeout_ms: int,
    message: str,
) -> T:
    errors.append(_partial_error(source, "timeout", message, timeout_ms=timeout_ms))
    return default


def _partial_error(
    source: str,
    reason: str,
    message: str,
    *,
    timeout_ms: int | None = None,
    status_code: int | None = None,
) -> BffPartialError:
    return BffPartialError(
        source=_monitor_partial_source_name(source),
        detail=_monitor_partial_detail(reason),
        reason=_monitor_partial_reason(reason),
        status_code=status_code,
        timeout_ms=timeout_ms,
        fallback_source="python_local",
        message=str(message or "")[:240],
    )


def _monitor_partial_source_name(source: str) -> str:
    if source == "monitor_review":
        return "review"
    return source


def _monitor_partial_detail(reason: str) -> str:
    if reason == "timeout":
        return "数据源超时，已保留主数据并降级显示。"
    if reason == "status":
        return "数据源状态异常，已保留主数据并降级显示。"
    return "数据源暂时不可用，已保留主数据并降级显示。"


def _monitor_partial_reason(reason: str) -> str:
    if reason in {"timeout", "status", "error"}:
        return reason
    return "other"


def _attached_user(db: Session, user: User) -> User:
    user_id = 0
    try:
        identity = sa_inspect(user).identity
        if identity:
            user_id = int(identity[0] or 0)
    except Exception:
        user_dict = getattr(user, "__dict__", {})
        if isinstance(user_dict, dict):
            try:
                user_id = int(user_dict.get("id") or 0)
            except Exception:
                user_id = 0
    if user_id <= 0:
        try:
            user_id = int(getattr(user, "id", 0) or 0)
        except Exception:
            user_id = 0
    if user_id <= 0:
        return user
    try:
        refreshed = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    except Exception:
        return user
    return refreshed or user


def _remote_adapter_allowed(request: Request) -> bool:
    expected = get_settings().tquant_internal_service_token.strip()
    provided = request.headers.get("X-Internal-Service-Token", "").strip()
    return not (request.headers.get("X-TQuant-Bff-Hop") == "1" and expected and provided == expected)


def _record_partial_errors(response: object) -> None:
    for error in getattr(response, "partial_errors", []) or []:
        source = getattr(error, "source", "")
        reason = getattr(error, "reason", "other")
        if isinstance(error, dict):
            source = str(error.get("source") or source)
            reason = str(error.get("reason") or reason)
        record_bff_partial_failure(str(source), str(reason))


def _bff_timeout_seconds() -> float:
    return float(getattr(get_settings(), "bff_workspace_timeout_seconds", 8.0) or 8.0)


def _monitor_priority_item_count(response: MonitorWorkspaceBffResponse) -> int:
    if response.monitor_snapshot is None:
        return 0
    board = response.monitor_snapshot.priority_board
    if isinstance(board, dict) and isinstance(board.get("items"), list):
        return len(board["items"])
    return 0


def _settings_admin_enabled(
    *,
    request: Request,
    current_user: User,
    x_admin_token: str | None,
    authorization: str | None,
) -> bool:
    if is_admin_user(current_user):
        return True
    try:
        require_admin_auth(request, x_admin_token=x_admin_token, authorization=authorization)
        return True
    except HTTPException:
        return False
