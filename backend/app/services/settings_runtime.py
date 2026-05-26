from __future__ import annotations

from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.orm import Session

from app.core.config import RUNTIME_ENV_PATH, get_settings
from app.models.schema_defs.settings import RuntimeStatusResponse
from app.services.db_admin_service import DatabaseAdminService
from app.services.settings_service import SettingsService

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIST_INDEX = PROJECT_ROOT / "frontend" / "dist" / "index.html"


class SettingsRuntimeDiagnosticsService:
    """Runtime diagnostics seam for Settings UI and BFF callers."""

    def __init__(self, db: Session, db_admin_service: DatabaseAdminService | None = None) -> None:
        self.db = db
        self.db_admin_service = db_admin_service or DatabaseAdminService()

    def build_status(self) -> RuntimeStatusResponse:
        settings = get_settings()
        payload = SettingsService(self.db).get_payload()
        database_url = settings.database_url
        runtime_overrides = _runtime_overrides()
        runtime_database_url = runtime_overrides.get("DATABASE_URL", "")
        runtime_database_matches_settings = _runtime_database_matches(
            runtime_database_url=runtime_database_url,
            payload_database_url=payload.database_url,
            settings_database_url=database_url,
        )
        runtime_llm_secret_persisted = "LLM_API_KEY" in runtime_overrides
        consistency_ok = runtime_database_matches_settings and not runtime_llm_secret_persisted
        ready_checks = {
            "database": self._database_ready(database_url),
            "frontend_dist": FRONTEND_DIST_INDEX.exists(),
            "runtime_consistency": consistency_ok,
        }
        consistency_status, consistency_text = _consistency_status_text(
            runtime_database_url=runtime_database_url,
            runtime_database_matches_settings=runtime_database_matches_settings,
            runtime_llm_secret_persisted=runtime_llm_secret_persisted,
        )
        return RuntimeStatusResponse(
            app_name=settings.app_name,
            api_prefix=settings.api_prefix,
            database_backend=self._database_backend(database_url),
            database_url_masked=self.db_admin_service.mask_database_url(database_url),
            runtime_database_url_masked=self.db_admin_service.mask_database_url(runtime_database_url) if runtime_database_url else "",
            runtime_env_path=str(RUNTIME_ENV_PATH),
            runtime_env_exists=RUNTIME_ENV_PATH.exists(),
            runtime_database_override="DATABASE_URL" in runtime_overrides,
            runtime_database_matches_settings=runtime_database_matches_settings,
            runtime_llm_secret_persisted=runtime_llm_secret_persisted,
            settings_consistency_status=consistency_status,
            settings_consistency_text=consistency_text,
            frontend_dist_path=str(FRONTEND_DIST_INDEX),
            frontend_dist_ready=FRONTEND_DIST_INDEX.exists(),
            llm_configured=bool(payload.llm_api_key.strip() and payload.llm_base_url.strip() and payload.llm_model.strip()),
            data_source=payload.data_source,
            data_source_base_url=payload.data_source_base_url,
            cors_origins=settings.cors_origins,
            ready_checks=ready_checks,
        )

    def _database_ready(self, database_url: str) -> bool:
        try:
            self.db_admin_service.check_connection(database_url)
            return True
        except Exception:
            return False

    def _database_backend(self, database_url: str) -> str:
        engine_bundle = self.db_admin_service._build_engine_bundle(database_url)
        try:
            return engine_bundle.engine.url.get_backend_name()
        finally:
            engine_bundle.engine.dispose()


def _runtime_overrides() -> dict[str, str]:
    if not RUNTIME_ENV_PATH.exists():
        return {}
    return {key: value for key, value in dotenv_values(RUNTIME_ENV_PATH).items() if value is not None}


def _runtime_database_matches(
    *,
    runtime_database_url: str,
    payload_database_url: str,
    settings_database_url: str,
) -> bool:
    if not runtime_database_url:
        return True
    return runtime_database_url.strip() in {payload_database_url.strip(), settings_database_url.strip()}


def _consistency_status_text(
    *,
    runtime_database_url: str,
    runtime_database_matches_settings: bool,
    runtime_llm_secret_persisted: bool,
) -> tuple[str, str]:
    problems: list[str] = []
    if runtime_database_url and not runtime_database_matches_settings:
        problems.append("runtime.env 的 DATABASE_URL 与当前设置不一致")
    if runtime_llm_secret_persisted:
        problems.append("runtime.env 中仍存在 LLM_API_KEY，已不符合敏感字段持久化策略")
    if problems:
        return "warning", "；".join(problems)
    if runtime_database_url:
        return "ok", "runtime.env 数据库覆盖与当前设置一致，敏感字段未明文持久化"
    return "ok", "未启用 runtime.env 数据库覆盖，敏感字段未明文持久化"
