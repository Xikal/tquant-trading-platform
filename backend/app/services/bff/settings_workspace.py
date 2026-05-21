from __future__ import annotations

from typing import Callable, TypeVar

from sqlalchemy.orm import Session

from app.core.admin_auth import is_admin_token_configured
from app.core.timezone import beijing_now_string
from app.models.entities import User
from app.models.schema_defs.bff import BffPartialError, SettingsWorkspaceBffResponse
from app.services.low_buy.strategy_governance import build_low_buy_strategy_governance
from app.services.settings_admin_snapshot import build_admin_metrics_snapshot, build_admin_task_snapshot
from app.services.settings_factor_weights import SettingsFactorWeightsService
from app.services.settings_runtime import SettingsRuntimeDiagnosticsService
from app.services.settings_service import SettingsService
from app.services.user_sector_preferences import UserSectorPreferenceService

T = TypeVar("T")


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
        settings=_safe(
            "settings",
            errors,
            lambda: SettingsService(db).get_public_payload(admin_auth_required=is_admin_token_configured()),
        ),
        sector_exclusions=_safe(
            "sector_exclusions",
            errors,
            lambda: UserSectorPreferenceService(db).build_response(current_user.id),
        ),
        strategy_governance=_safe("strategy_governance", errors, lambda: build_low_buy_strategy_governance(db)),
        runtime=_safe("runtime", errors, lambda: SettingsRuntimeDiagnosticsService(db).build_status()) if include_admin else None,
        factor_weights=_safe("factor_weights", errors, SettingsFactorWeightsService().build_response)
        if include_admin
        else None,
        admin_tasks=_safe("admin_tasks", errors, build_admin_task_snapshot) if include_admin else None,
        admin_metrics=_safe("admin_metrics", errors, lambda: build_admin_metrics_snapshot(db)) if include_admin else None,
        admin_enabled=include_admin,
        partial_errors=errors,
    )


def _safe(source: str, errors: list[BffPartialError], loader: Callable[[], T]) -> T | None:
    try:
        return loader()
    except Exception:
        errors.append(BffPartialError(source=source, detail="数据暂时不可用"))
        return None
