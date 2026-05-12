from __future__ import annotations

from app.core.config import AppSettings


def validate_security_settings(settings: AppSettings) -> None:
    """Fail fast for production-like insecure auth cookie settings."""

    if not _production_like(settings):
        return
    if not settings.auth_cookie_secure:
        raise RuntimeError("生产环境必须启用 AUTH_COOKIE_SECURE=true")
    if settings.auth_cookie_samesite.strip().lower() != "strict":
        raise RuntimeError("生产环境必须启用 AUTH_COOKIE_SAMESITE=strict")


def _production_like(settings: AppSettings) -> bool:
    env = settings.app_environment.strip().lower()
    if env in {"prod", "production", "cloud"}:
        return True
    origins = [item.lower() for item in settings.cors_origins]
    return any("localhost" not in item and "127.0.0.1" not in item for item in origins)
