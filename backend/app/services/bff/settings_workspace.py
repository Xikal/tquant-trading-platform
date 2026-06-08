from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

from sqlalchemy.orm import Session

from app.core.admin_auth import is_admin_token_configured
from app.core.database import SessionLocal
from app.core.timezone import beijing_now_string
from app.models.entities import User
from app.models.schema_defs.bff import BffPartialError, SettingsWorkspaceBffResponse
from app.services.bff.timeout import run_workspace_with_timeout
from app.services.low_buy.strategy_governance import build_low_buy_strategy_governance
from app.services.settings_admin_snapshot import build_admin_metrics_snapshot, build_admin_task_snapshot
from app.services.settings_factor_weights import SettingsFactorWeightsService
from app.services.settings_runtime import SettingsRuntimeDiagnosticsService
from app.services.settings_service import SettingsService
from app.services.user_sector_preferences import UserSectorPreferenceService

T = TypeVar("T")
logger = logging.getLogger(__name__)
SETTINGS_WORKSPACE_SOURCE_TIMEOUT_MS = {
    "settings": 800,
    "sector_exclusions": 1_000,
    "strategy_governance": 1_000,
    "runtime": 1_200,
    "factor_weights": 500,
    "admin_tasks": 500,
    "admin_metrics": 1_200,
}


def build_settings_workspace(
    db: Session,
    *,
    current_user: User,
    include_admin: bool,
) -> SettingsWorkspaceBffResponse:
    """Build the Settings page payload behind one frontend-specific seam."""

    errors: list[BffPartialError] = []
    return SettingsWorkspaceBffResponse(
        generated_at=beijing_now_string(),
        settings=_safe_budgeted(
            "settings",
            errors,
            lambda: _run_db_source(
                db,
                lambda source_db: SettingsService(source_db).get_public_payload(admin_auth_required=is_admin_token_configured()),
            ),
        ),
        sector_exclusions=_safe_budgeted(
            "sector_exclusions",
            errors,
            lambda: _run_db_source(db, lambda source_db: UserSectorPreferenceService(source_db).build_response(current_user.id)),
        ),
        strategy_governance=_safe_budgeted("strategy_governance", errors, lambda: _run_db_source(db, build_low_buy_strategy_governance)),
        runtime=_safe_budgeted("runtime", errors, lambda: _run_db_source(db, lambda source_db: SettingsRuntimeDiagnosticsService(source_db).build_status()))
        if include_admin
        else None,
        factor_weights=_safe_budgeted("factor_weights", errors, SettingsFactorWeightsService().build_response)
        if include_admin
        else None,
        admin_tasks=_safe_budgeted("admin_tasks", errors, build_admin_task_snapshot) if include_admin else None,
        admin_metrics=_safe_budgeted("admin_metrics", errors, lambda: _run_db_source(db, build_admin_metrics_snapshot)) if include_admin else None,
        admin_enabled=include_admin,
        partial_errors=errors,
    )


def _safe(source: str, errors: list[BffPartialError], loader: Callable[[], T]) -> T | None:
    try:
        return loader()
    except Exception:
        errors.append(BffPartialError(source=source, detail="数据暂时不可用"))
        return None


def _safe_budgeted(source: str, errors: list[BffPartialError], loader: Callable[[], T]) -> T | None:
    timeout_ms = int(SETTINGS_WORKSPACE_SOURCE_TIMEOUT_MS.get(source) or 0)
    if timeout_ms <= 0:
        return _safe(source, errors, loader)
    started = time.perf_counter()
    return run_workspace_with_timeout(
        source=source,
        timeout_seconds=timeout_ms / 1000.0,
        loader=loader,
        fallback=lambda error: _record_timeout(
            source,
            errors,
            timeout_ms=error.timeout_ms or timeout_ms,
            started=started,
        ),
    )


def _record_timeout(
    source: str,
    errors: list[BffPartialError],
    *,
    timeout_ms: int,
    started: float,
) -> None:
    errors.append(
        BffPartialError(
            source=source,
            detail="数据源超时，已返回首屏可用的降级结果",
            reason="timeout",
            timeout_ms=timeout_ms,
            fallback_source="python_local",
            message="workspace source timeout",
            elapsed_ms=max(0, int((time.perf_counter() - started) * 1000)),
        )
    )
    logger.warning("settings workspace source timed out source=%s timeout_ms=%s", source, timeout_ms)
    return None


def _run_db_source(db: Session, loader: Callable[[Session], T]) -> T:
    if not _threaded_db_source_allowed(db):
        return loader(db)
    with SessionLocal() as source_db:
        return loader(source_db)


def _threaded_db_source_allowed(db: Session) -> bool:
    try:
        url = str(db.get_bind().url)
    except Exception:
        return False
    return url not in {"sqlite:///:memory:", "sqlite://"}
