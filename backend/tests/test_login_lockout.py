from __future__ import annotations

from os import environ

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.models.base import Base
from app.services.auth_service import AuthError, AuthService


def test_login_lockout_after_repeated_failures() -> None:
    environ["AUTH_SECRET_KEY"] = "login-lockout-secret-0123456789abcdef0123456789abcdef0123456789abcdef"
    environ["AUTH_LOGIN_LOCKOUT_THRESHOLD"] = "2"
    environ["AUTH_LOGIN_LOCKOUT_MINUTES"] = "15"
    get_settings.cache_clear()
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    service = AuthService()
    with Session() as db:
        service.register(db, username="lockout_user", password="secret123")
        for _ in range(2):
            with pytest.raises(AuthError):
                service.login(db, username="lockout_user", password="bad-password")
        with pytest.raises(AuthError, match="锁定"):
            service.login(db, username="lockout_user", password="secret123")
    environ.pop("AUTH_LOGIN_LOCKOUT_THRESHOLD", None)
    environ.pop("AUTH_LOGIN_LOCKOUT_MINUTES", None)
    get_settings.cache_clear()
