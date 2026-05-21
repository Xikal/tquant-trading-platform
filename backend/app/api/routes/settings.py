from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.admin_auth import is_admin_token_configured, require_admin_auth
from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.schemas import (
    DatabaseCheckRequest,
    DatabaseMigrationRequest,
    FactorWeightsResponse,
    FactorWeightsUpdate,
    SettingsUpdate,
    UserSectorExclusionsResponse,
    UserSectorExclusionsUpdate,
)
from app.models.entities import User
from app.services.db_admin_service import DatabaseAdminService
from app.services.settings_factor_weights import SettingsFactorWeightsService
from app.services.settings_runtime import SettingsRuntimeDiagnosticsService
from app.services.settings_service import SettingsService
from app.services.user_sector_preferences import UserSectorPreferenceService

router = APIRouter(dependencies=[Depends(get_current_user)])
db_admin_service = DatabaseAdminService()
settings = get_settings()


@router.get("/settings")
def get_settings(
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
):
    return SettingsService(db).get_public_payload(
        admin_auth_required=is_admin_token_configured()
    ).model_dump()


@router.put("/settings")
def update_settings(
    payload: SettingsUpdate,
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
):
    updated = SettingsService(db).update_payload(payload)
    return {
        "message": "配置已保存",
        "settings": SettingsService(db).get_public_payload(
            admin_auth_required=is_admin_token_configured()
        ).model_dump(),
        "restart_required": _requires_database_restart(payload.database_url),
    }


@router.get("/settings/sector-exclusions", response_model=UserSectorExclusionsResponse)
def get_sector_exclusions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return UserSectorPreferenceService(db).build_response(current_user.id)


@router.put("/settings/sector-exclusions", response_model=UserSectorExclusionsResponse)
def update_sector_exclusions(
    payload: UserSectorExclusionsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        UserSectorPreferenceService(db).replace_excluded_sectors(
            current_user.id,
            payload.excluded_sectors,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UserSectorPreferenceService(db).build_response(current_user.id)


@router.post("/settings/database/check")
def check_database(
    payload: DatabaseCheckRequest,
    _: None = Depends(require_admin_auth),
):
    try:
        return db_admin_service.check_connection(payload.database_url).model_dump()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/settings/database/migrate")
def migrate_database(
    payload: DatabaseMigrationRequest,
    _: None = Depends(require_admin_auth),
):
    try:
        result = db_admin_service.migrate_data(
            source_database_url=payload.source_database_url,
            target_database_url=payload.target_database_url,
            overwrite=payload.overwrite,
        )
        if payload.activate_on_restart:
            SettingsService.persist_runtime_database_url(payload.target_database_url)
            result.activated_on_restart = True
            result.message = "数据迁移完成，目标数据库已写入运行时配置，重启后端后生效。"
        return result.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/settings/runtime")
def get_runtime_status(
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
):
    return SettingsRuntimeDiagnosticsService(db, db_admin_service).build_status()


@router.get("/settings/factor-weights", response_model=FactorWeightsResponse)
def get_factor_weights(
    _: None = Depends(require_admin_auth),
) -> FactorWeightsResponse:
    return SettingsFactorWeightsService().build_response()


@router.put("/settings/factor-weights", response_model=FactorWeightsResponse)
def update_factor_weights(
    payload: FactorWeightsUpdate,
    _: None = Depends(require_admin_auth),
) -> FactorWeightsResponse:
    return SettingsFactorWeightsService().update_response(payload)


def _requires_database_restart(database_url: Optional[str]) -> bool:
    if database_url is None:
        return False
    cleaned = database_url.strip()
    return bool(cleaned and "***" not in cleaned)
