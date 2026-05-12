from __future__ import annotations

import pytest

from app.core.config import AppSettings
from app.core.security_config import validate_security_settings


def test_production_requires_secure_refresh_cookie() -> None:
    settings = AppSettings(
        app_environment="production",
        auth_cookie_secure=False,
        auth_cookie_samesite="strict",
        auth_secret_key="test-secret",
    )

    with pytest.raises(RuntimeError):
        validate_security_settings(settings)


def test_production_accepts_secure_strict_cookie() -> None:
    settings = AppSettings(
        app_environment="production",
        auth_cookie_secure=True,
        auth_cookie_samesite="strict",
        auth_secret_key="test-secret",
    )

    validate_security_settings(settings)
