from pathlib import Path
from typing import Optional

from dotenv import dotenv_values
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.admin_auth import is_admin_token_configured, require_admin_auth
from app.core.config import RUNTIME_ENV_PATH, get_settings
from app.core.database import get_db
from app.models.schemas import (
    DatabaseCheckRequest,
    DatabaseMigrationRequest,
    RuntimeStatusResponse,
    SettingsUpdate,
)
from app.services.db_admin_service import DatabaseAdminService
from app.services.settings_service import SettingsService

router = APIRouter()
db_admin_service = DatabaseAdminService()
settings = get_settings()
PROJECT_ROOT = Path(__file__).resolve().parents[4]
FRONTEND_DIST_INDEX = PROJECT_ROOT / "frontend" / "dist" / "index.html"


@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
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


@router.get("/settings/runtime", response_model=RuntimeStatusResponse)
def get_runtime_status(db: Session = Depends(get_db)):
    payload = SettingsService(db).get_payload()
    database_url = settings.database_url
    llm_configured = bool(
        payload.llm_api_key.strip() and payload.llm_base_url.strip() and payload.llm_model.strip()
    )
    runtime_overrides = (
        {
            key: value
            for key, value in dotenv_values(RUNTIME_ENV_PATH).items()
            if value is not None
        }
        if RUNTIME_ENV_PATH.exists()
        else {}
    )
    ready_checks = {
        "database": False,
        "frontend_dist": FRONTEND_DIST_INDEX.exists(),
    }
    try:
        db_admin_service.check_connection(database_url)
        ready_checks["database"] = True
    except Exception:
        ready_checks["database"] = False

    engine_bundle = db_admin_service._build_engine_bundle(database_url)
    try:
        database_backend = engine_bundle.engine.url.get_backend_name()
    finally:
        engine_bundle.engine.dispose()

    return RuntimeStatusResponse(
        app_name=settings.app_name,
        api_prefix=settings.api_prefix,
        database_backend=database_backend,
        database_url_masked=db_admin_service.mask_database_url(database_url),
        runtime_env_path=str(RUNTIME_ENV_PATH),
        runtime_env_exists=RUNTIME_ENV_PATH.exists(),
        runtime_database_override="DATABASE_URL" in runtime_overrides,
        frontend_dist_path=str(FRONTEND_DIST_INDEX),
        frontend_dist_ready=FRONTEND_DIST_INDEX.exists(),
        llm_configured=llm_configured,
        data_source=payload.data_source,
        data_source_base_url=payload.data_source_base_url,
        cors_origins=settings.cors_origins,
        ready_checks=ready_checks,
    )


def _requires_database_restart(database_url: Optional[str]) -> bool:
    if database_url is None:
        return False
    cleaned = database_url.strip()
    return bool(cleaned and "***" not in cleaned)
