from __future__ import annotations

from app.core.config import AppSettings

_MIN_AUTH_SECRET_LENGTH = 64
_WEAK_AUTH_SECRETS = {"default_secret", "tquant_secret_2024", "test-secret", "test-auth-secret"}


def validate_security_settings(settings: AppSettings) -> None:
    """Fail fast for production-like insecure auth cookie settings."""

    if settings.app_workers > 1 and (settings.global_rate_limit_backend or "memory").strip().lower() == "memory":
        raise RuntimeError("多 worker 部署必须配置 GLOBAL_RATE_LIMIT_BACKEND=redis 或网关限流")
    if not _production_like(settings):
        return
    if not settings.auth_cookie_secure and not settings.auth_allow_insecure_http_cookie:
        raise RuntimeError("生产环境必须启用 AUTH_COOKIE_SECURE=true")
    if settings.auth_cookie_samesite.strip().lower() != "strict":
        raise RuntimeError("生产环境必须启用 AUTH_COOKIE_SAMESITE=strict")
    if _weak_auth_secret(settings.auth_secret_key):
        raise RuntimeError("生产环境 AUTH_SECRET_KEY 必须配置为不少于 64 字符的非默认强密钥")
    if (settings.global_rate_limit_backend or "memory").strip().lower() == "memory":
        raise RuntimeError("生产环境 GLOBAL_RATE_LIMIT_BACKEND 不能使用 memory，请使用 redis 或网关限流")
    if _microservice_urls_configured(settings) and not settings.tquant_internal_service_token.strip():
        raise RuntimeError("配置微服务 URL 时必须设置 TQUANT_INTERNAL_SERVICE_TOKEN")
    if _weak_auth_secret(settings.tquant_settings_encryption_key):
        raise RuntimeError("生产环境 TQUANT_SETTINGS_ENCRYPTION_KEY 必须配置为不少于 64 字符的独立强密钥")
    if settings.tquant_settings_encryption_key.strip() == settings.auth_secret_key.strip():
        raise RuntimeError("TQUANT_SETTINGS_ENCRYPTION_KEY 必须与 AUTH_SECRET_KEY 解耦")


def _production_like(settings: AppSettings) -> bool:
    env = settings.app_environment.strip().lower()
    if env in {"prod", "production", "cloud"}:
        return True
    origins = [item.lower() for item in settings.cors_origins]
    return any("localhost" not in item and "127.0.0.1" not in item for item in origins)


def _weak_auth_secret(secret: str) -> bool:
    clean = secret.strip()
    return len(clean) < _MIN_AUTH_SECRET_LENGTH or clean in _WEAK_AUTH_SECRETS


def _microservice_urls_configured(settings: AppSettings) -> bool:
    return any(
        str(value).strip()
        for value in (
            settings.tquant_market_service_url,
            settings.tquant_bff_gateway_url,
            settings.tquant_market_read_service_url,
            settings.tquant_go_scan_worker_url,
            settings.tquant_strategy_service_url,
            settings.tquant_backtest_service_url,
            settings.tquant_trade_service_url,
            settings.tquant_factor_service_url,
            settings.tquant_admin_service_url,
        )
    )
