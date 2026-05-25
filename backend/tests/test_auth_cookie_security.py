from __future__ import annotations

import pytest

from app.core.config import AppSettings
from app.core.security_config import validate_security_settings

STRONG_TEST_SECRET = "test-secret-0123456789abcdef0123456789abcdef0123456789abcdef012345"
STRONG_SETTINGS_SECRET = "settings-secret-0123456789abcdef0123456789abcdef0123456789abcdef"


def test_production_requires_secure_refresh_cookie() -> None:
    settings = AppSettings(
        app_environment="production",
        auth_cookie_secure=False,
        auth_cookie_samesite="strict",
        auth_secret_key=STRONG_TEST_SECRET,
        tquant_settings_encryption_key=STRONG_SETTINGS_SECRET,
        global_rate_limit_backend="redis",
    )

    with pytest.raises(RuntimeError):
        validate_security_settings(settings)


def test_production_accepts_secure_strict_cookie() -> None:
    settings = AppSettings(
        app_environment="production",
        auth_cookie_secure=True,
        auth_cookie_samesite="strict",
        auth_secret_key=STRONG_TEST_SECRET,
        tquant_settings_encryption_key=STRONG_SETTINGS_SECRET,
        global_rate_limit_backend="redis",
    )

    validate_security_settings(settings)


def test_production_rejects_weak_auth_secret() -> None:
    settings = AppSettings(
        app_environment="production",
        auth_cookie_secure=True,
        auth_cookie_samesite="strict",
        auth_secret_key="tquant_secret_2024",
        tquant_settings_encryption_key=STRONG_SETTINGS_SECRET,
        global_rate_limit_backend="redis",
    )

    with pytest.raises(RuntimeError, match="AUTH_SECRET_KEY"):
        validate_security_settings(settings)


def test_production_rejects_memory_rate_limit() -> None:
    settings = AppSettings(
        app_environment="production",
        auth_cookie_secure=True,
        auth_cookie_samesite="strict",
        auth_secret_key=STRONG_TEST_SECRET,
        tquant_settings_encryption_key=STRONG_SETTINGS_SECRET,
        global_rate_limit_backend="memory",
    )

    with pytest.raises(RuntimeError, match="GLOBAL_RATE_LIMIT_BACKEND"):
        validate_security_settings(settings)


def test_multi_worker_rejects_memory_rate_limit_even_outside_production() -> None:
    settings = AppSettings(
        app_environment="development",
        auth_cookie_secure=False,
        auth_cookie_samesite="lax",
        auth_secret_key="",
        tquant_settings_encryption_key="",
        app_workers=4,
        global_rate_limit_backend="memory",
    )

    with pytest.raises(RuntimeError, match="多 worker"):
        validate_security_settings(settings)


def test_production_requires_internal_token_for_microservice_urls() -> None:
    settings = AppSettings(
        app_environment="production",
        auth_cookie_secure=True,
        auth_cookie_samesite="strict",
        auth_secret_key=STRONG_TEST_SECRET,
        tquant_settings_encryption_key=STRONG_SETTINGS_SECRET,
        global_rate_limit_backend="redis",
        tquant_trade_service_url="http://trade-service",
    )

    with pytest.raises(RuntimeError, match="TQUANT_INTERNAL_SERVICE_TOKEN"):
        validate_security_settings(settings)


def test_production_requires_separate_settings_encryption_key() -> None:
    settings = AppSettings(
        app_environment="production",
        auth_cookie_secure=True,
        auth_cookie_samesite="strict",
        auth_secret_key=STRONG_TEST_SECRET,
        tquant_settings_encryption_key=STRONG_TEST_SECRET,
        global_rate_limit_backend="redis",
    )

    with pytest.raises(RuntimeError, match="TQUANT_SETTINGS_ENCRYPTION_KEY"):
        validate_security_settings(settings)
