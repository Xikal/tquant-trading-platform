import json
from pathlib import Path
from typing import Any
from urllib.parse import SplitResult, urlsplit, urlunsplit

from dotenv import dotenv_values
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import RUNTIME_ENV_PATH
from app.models.entities import SystemSetting
from app.models.schemas import SettingsPayload, SettingsUpdate
from app.services.secret_field_crypto import decrypt_secret_field, encrypt_secret_field


DEFAULT_RUNTIME_SETTINGS = SettingsPayload()
MASKED_SECRET = "********"
SENSITIVE_SETTING_FIELDS = {"llm_api_key", "database_url"}
RUNTIME_ENV_KEY_MAP = {
    "llm_provider": "LLM_PROVIDER",
    "database_url": "DATABASE_URL",
    "llm_api_key": "LLM_API_KEY",
    "llm_base_url": "LLM_BASE_URL",
    "llm_model": "LLM_MODEL",
    "data_source": "DEFAULT_DATA_SOURCE",
    "data_source_base_url": "DATA_SOURCE_BASE_URL",
}
RUNTIME_ENV_PERSIST_KEY_MAP = {
    key: value
    for key, value in RUNTIME_ENV_KEY_MAP.items()
    if key != "llm_api_key"
}
SENSITIVE_RUNTIME_ENV_KEYS_TO_DROP = {"LLM_API_KEY"}


class SettingsService:
    def __init__(self, db: Session):
        self.db = db

    def get_payload(self) -> SettingsPayload:
        payload = DEFAULT_RUNTIME_SETTINGS.model_dump()
        payload.update(self._load_runtime_overrides(payload))
        rows = self.db.execute(select(SystemSetting)).scalars().all()
        for row in rows:
            if row.key in payload:
                payload[row.key] = self._coerce_value(row.key, self._decrypt_if_sensitive(row.key, row.value), payload[row.key])
        return SettingsPayload(**payload)

    def get_public_payload(self, *, admin_auth_required: bool = False) -> SettingsPayload:
        payload = self.get_payload().model_dump()
        payload["llm_api_key_configured"] = bool(payload.get("llm_api_key", "").strip())
        payload["database_url_configured"] = bool(payload.get("database_url", "").strip())
        payload["admin_auth_required"] = admin_auth_required
        payload["llm_api_key"] = MASKED_SECRET if payload["llm_api_key_configured"] else ""
        payload["database_url"] = _mask_database_url(payload.get("database_url", ""))
        return SettingsPayload(**payload)

    def update_payload(self, update: SettingsUpdate) -> SettingsPayload:
        current = self.get_payload().model_dump()
        changes = _drop_masked_sensitive_values(update.model_dump(exclude_none=True))
        current.update(changes)

        for key, value in changes.items():
            row = self.db.execute(
                select(SystemSetting).where(SystemSetting.key == key)
            ).scalar_one_or_none()
            if row is None:
                row = SystemSetting(key=key, value=self._serialize_setting_value(key, value))
                self.db.add(row)
            else:
                row.value = self._serialize_setting_value(key, value)

        self.db.commit()
        runtime_keys = set(changes) & set(RUNTIME_ENV_KEY_MAP)
        if runtime_keys:
            self.persist_runtime_settings(current)
        return SettingsPayload(**current)

    @staticmethod
    def _load_runtime_overrides(payload: dict[str, Any]) -> dict[str, Any]:
        if not RUNTIME_ENV_PATH.exists():
            return {}

        overrides = {
            key: value for key, value in dotenv_values(RUNTIME_ENV_PATH).items() if value is not None
        }
        merged: dict[str, Any] = {}
        for field_name, env_name in RUNTIME_ENV_KEY_MAP.items():
            raw_value = overrides.get(env_name)
            if raw_value in (None, ""):
                continue
            merged[field_name] = SettingsService._coerce_value(
                field_name, raw_value, payload[field_name]
            )
        return merged

    @staticmethod
    def _serialize_value(value: Any) -> str:
        if isinstance(value, bool):
            return json.dumps(value)
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    @staticmethod
    def _serialize_setting_value(key: str, value: Any) -> str:
        serialized = SettingsService._serialize_value(value)
        return encrypt_secret_field(serialized) if key in SENSITIVE_SETTING_FIELDS else serialized

    @staticmethod
    def _decrypt_if_sensitive(key: str, value: str) -> str:
        return decrypt_secret_field(value) if key in SENSITIVE_SETTING_FIELDS else value

    @staticmethod
    def _coerce_value(key: str, raw: str, default: Any) -> Any:
        if isinstance(default, bool):
            return str(raw).lower() in {"1", "true", "yes", "on"}
        if isinstance(default, int) and not isinstance(default, bool):
            try:
                return int(raw)
            except ValueError:
                return int(float(raw))
        if isinstance(default, float):
            return float(raw)
        if isinstance(default, (dict, list)):
            return json.loads(raw)
        return raw

    @staticmethod
    def persist_runtime_settings(payload: dict[str, Any]) -> None:
        existing = {}
        if RUNTIME_ENV_PATH.exists():
            existing = {
                key: value
                for key, value in dotenv_values(RUNTIME_ENV_PATH).items()
                if value is not None
            }

        for env_name in SENSITIVE_RUNTIME_ENV_KEYS_TO_DROP:
            existing.pop(env_name, None)

        for field_name, env_name in RUNTIME_ENV_PERSIST_KEY_MAP.items():
            if field_name not in payload:
                continue
            raw_value = payload.get(field_name, "")
            cleaned_value = raw_value.strip() if isinstance(raw_value, str) else str(raw_value)
            if cleaned_value:
                existing[env_name] = cleaned_value
            else:
                existing.pop(env_name, None)

        RUNTIME_ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# Auto-generated runtime overrides. Restart backend after editing.\n"]
        for key in sorted(existing):
            value = existing[key]
            lines.append(f"{key}={json.dumps(value, ensure_ascii=False)}\n")
        Path(RUNTIME_ENV_PATH).write_text("".join(lines), encoding="utf-8")

    @staticmethod
    def persist_runtime_database_url(database_url: str) -> None:
        SettingsService.persist_runtime_settings({"database_url": database_url})


def _drop_masked_sensitive_values(changes: dict[str, Any]) -> dict[str, Any]:
    filtered = dict(changes)
    for field_name in SENSITIVE_SETTING_FIELDS:
        value = filtered.get(field_name)
        if value is None:
            continue
        if _is_masked_or_empty_secret(str(value)):
            filtered.pop(field_name, None)
    return filtered


def _is_masked_or_empty_secret(value: str) -> bool:
    cleaned = value.strip()
    return not cleaned or cleaned == MASKED_SECRET or "***" in cleaned


def _mask_database_url(database_url: str) -> str:
    if not database_url:
        return ""
    try:
        parts = urlsplit(database_url)
    except ValueError:
        return MASKED_SECRET
    if not parts.scheme or not parts.netloc:
        return MASKED_SECRET
    hostname = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    username = parts.username or ""
    auth = f"{username}:***@" if username else ""
    masked = SplitResult(
        scheme=parts.scheme,
        netloc=f"{auth}{hostname}{port}",
        path=parts.path,
        query="",
        fragment="",
    )
    return urlunsplit(masked)
