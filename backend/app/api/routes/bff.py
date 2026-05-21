from __future__ import annotations

import logging
from typing import Callable, TypeVar

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.routes.market import market_breadth, paired_hedge_research, sector_relative_strength
from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.paper_auth import require_paper_trading
from app.core.admin_auth import require_admin_auth
from app.core.role_permissions import is_admin_user
from app.core.timezone import beijing_now_string
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
from app.services.bff.settings_workspace import build_settings_workspace
from app.services.bff.strategy_workspace import build_strategy_workspace
from app.services.bff.timeout import run_workspace_with_timeout
from app.services.monitor_snapshot_service import build_monitor_snapshot

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bff/v1", dependencies=[Depends(get_current_user)])
T = TypeVar("T")


@router.get("/manifest", response_model=BffManifestResponse)
def bff_manifest() -> BffManifestResponse:
    """Expose the stable BFF contract consumed by Web/App frontends."""

    return BffManifestResponse(
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


@router.get("/workspace/monitor", response_model=MonitorWorkspaceBffResponse)
def monitor_workspace_bff(
    request: Request,
    priority_limit: int = Query(default=12, ge=1, le=30),
    sector_limit: int = Query(default=8, ge=1, le=20),
    per_sector_limit: int = Query(default=8, ge=1, le=30),
    hedge_limit: int = Query(default=4, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MonitorWorkspaceBffResponse:
    """Aggregate monitor first-screen data behind a frontend-specific seam."""

    if _remote_adapter_allowed(request):
        remote = load_remote_monitor_workspace(
            priority_limit=priority_limit,
            sector_limit=sector_limit,
            per_sector_limit=per_sector_limit,
            hedge_limit=hedge_limit,
            forward_headers=forwarded_request_headers(request.headers),
        )
        if remote is not None:
            return remote

    errors: list[BffPartialError] = []
    return MonitorWorkspaceBffResponse(
        generated_at=beijing_now_string(),
        monitor_snapshot=_safe(
            "monitor_snapshot",
            errors,
            lambda: build_monitor_snapshot(db, current_user=current_user, priority_limit=priority_limit),
        ),
        market_breadth=_safe("market_breadth", errors, market_breadth),
        sector_relative_strength=_safe(
            "sector_relative_strength",
            errors,
            lambda: sector_relative_strength(sector_limit, per_sector_limit, db),
        ),
        paired_hedge=_safe(
            "paired_hedge",
            errors,
            lambda: paired_hedge_research(hedge_limit, current_user, db),
        ),
        partial_errors=errors,
    )


@router.get("/workspace/paper", response_model=PaperWorkspaceBffResponse)
def paper_workspace_bff(
    request: Request,
    order_limit: int = Query(default=80, ge=1, le=200),
    trade_limit: int = Query(default=300, ge=1, le=300),
    run_limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> PaperWorkspaceBffResponse:
    """Aggregate the paper trading first-screen payload for Web/App clients."""

    if _remote_adapter_allowed(request):
        remote = load_remote_paper_workspace(
            order_limit=order_limit,
            trade_limit=trade_limit,
            run_limit=run_limit,
            forward_headers=forwarded_request_headers(request.headers),
        )
        if remote is not None:
            return remote

    return run_workspace_with_timeout(
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
    )


@router.get("/workspace/strategy", response_model=StrategyWorkspaceBffResponse)
def strategy_workspace_bff(
    request: Request,
    run_limit: int = Query(default=8, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StrategyWorkspaceBffResponse:
    """Aggregate StrategyHub first-screen data for Web/App clients."""

    if _remote_adapter_allowed(request):
        remote = load_remote_strategy_workspace(
            run_limit=run_limit,
            forward_headers=forwarded_request_headers(request.headers),
        )
        if remote is not None:
            return remote

    return run_workspace_with_timeout(
        source="strategy_workspace",
        timeout_seconds=_bff_timeout_seconds(),
        loader=lambda: build_strategy_workspace(db, current_user=current_user, run_limit=run_limit),
        fallback=lambda error: StrategyWorkspaceBffResponse(
            generated_at=beijing_now_string(),
            partial_errors=[error],
        ),
    )


@router.get("/workspace/settings", response_model=SettingsWorkspaceBffResponse)
def settings_workspace_bff(
    request: Request,
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
    if _remote_adapter_allowed(request):
        remote = load_remote_settings_workspace(
            include_admin=include_admin,
            forward_headers=forwarded_request_headers(request.headers),
        )
        if remote is not None:
            return remote

    return run_workspace_with_timeout(
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
    )


def _safe(source: str, errors: list[BffPartialError], loader: Callable[[], T]) -> T | None:
    try:
        return loader()
    except HTTPException as exc:
        errors.append(BffPartialError(source=source, detail=str(exc.detail)))
        return None
    except Exception as exc:
        logger.warning("bff source failed source=%s", source, exc_info=(type(exc), exc, exc.__traceback__))
        errors.append(BffPartialError(source=source, detail="数据暂时不可用"))
        return None


def _remote_adapter_allowed(request: Request) -> bool:
    expected = get_settings().tquant_internal_service_token.strip()
    provided = request.headers.get("X-Internal-Service-Token", "").strip()
    return not (request.headers.get("X-TQuant-Bff-Hop") == "1" and expected and provided == expected)


def _bff_timeout_seconds() -> float:
    return float(getattr(get_settings(), "bff_workspace_timeout_seconds", 8.0) or 8.0)


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
