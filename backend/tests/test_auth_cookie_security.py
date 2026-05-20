from __future__ import annotations

import pytest

from app.core.config import AppSettings
from app.core.security_config import validate_security_settings

STRONG_TEST_SECRET = "test-secret-0123456789abcdef0123456789abcdef0123456789abcdef012345"


def test_production_requires_secure_refresh_cookie() -> None:
    settings = AppSettings(
        app_environment="production",
        auth_cookie_secure=False,
        auth_cookie_samesite="strict",
        auth_secret_key=STRONG_TEST_SECRET,
    )

    with pytest.raises(RuntimeError):
        validate_security_settings(settings)


def test_production_accepts_secure_strict_cookie() -> None:
    settings = AppSettings(
        app_environment="production",
        auth_cookie_secure=True,
        auth_cookie_samesite="strict",
        auth_secret_key=STRONG_TEST_SECRET,
    )

    validate_security_settings(settings)


def test_production_rejects_weak_auth_secret() -> None:
    settings = AppSettings(
        app_environment="production",
        auth_cookie_secure=True,
        auth_cookie_samesite="strict",
        auth_secret_key="tquant_secret_2024",
    )

    with pytest.raises(RuntimeError, match="AUTH_SECRET_KEY"):
        validate_security_settings(settings)
