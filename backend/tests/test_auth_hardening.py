from __future__ import annotations

import secrets
from datetime import timedelta
from os import environ

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.models.base import Base
from app.models.entities import User, UserSession
from app.services.auth_service import (
    PASSWORD_ALGORITHM,
    PASSWORD_ITERATIONS,
    REFRESH_RETRY_GRACE_SECONDS,
    AuthError,
    AuthService,
    _b64encode,
    _hash_legacy_pbkdf2_password,
)

STRONG_TEST_SECRET = "auth-hardening-secret-0123456789abcdef0123456789abcdef0123456789abcdef"


@pytest.fixture()
def session_factory():
    original = environ.get("AUTH_SECRET_KEY")
    environ["AUTH_SECRET_KEY"] = STRONG_TEST_SECRET
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(bind=engine, future=True)
    finally:
        if original is None:
            environ.pop("AUTH_SECRET_KEY", None)
        else:
            environ["AUTH_SECRET_KEY"] = original
        get_settings.cache_clear()


def test_refresh_token_replay_revokes_all_user_sessions(session_factory) -> None:
    service = AuthService()
    with session_factory() as db:
        tokens = service.register(db, username="replay_user", password="secret123")
        rotated = service.refresh(db, tokens.refresh_token)
        assert rotated.access_token
        old_session = service._get_session_by_token(db, tokens.refresh_token)
        assert old_session is not None
        old_session.revoked_at = old_session.revoked_at - timedelta(seconds=REFRESH_RETRY_GRACE_SECONDS + 1)
        db.commit()

        with pytest.raises(AuthError, match="重放"):
            service.refresh(db, tokens.refresh_token)

        sessions = db.execute(select(UserSession)).scalars().all()
        assert sessions
        assert all(row.revoked_at is not None for row in sessions)


def test_recent_refresh_token_retry_does_not_revoke_rotated_session(session_factory) -> None:
    service = AuthService()
    with session_factory() as db:
        tokens = service.register(db, username="retry_user", password="secret123")
        rotated = service.refresh(db, tokens.refresh_token)
        assert rotated.access_token

        with pytest.raises(AuthError, match="登录凭证已轮换"):
            service.refresh(db, tokens.refresh_token)

        assert service.refresh(db, rotated.refresh_token).access_token
        sessions = db.execute(select(UserSession)).scalars().all()
        assert any(row.revoked_at is None for row in sessions)


def test_legacy_pbkdf2_password_rehashes_to_scrypt_after_login(session_factory) -> None:
    salt = secrets.token_bytes(16)
    legacy_hash = (
        f"pbkdf2_sha256${PASSWORD_ITERATIONS}${_b64encode(salt)}$"
        f"{_hash_legacy_pbkdf2_password('secret123', salt)}"
    )
    service = AuthService()
    with session_factory() as db:
        user = User(username="legacy_user", display_name="legacy", password_hash=legacy_hash)
        db.add(user)
        db.commit()

        service.login(db, username="legacy_user", password="secret123")

        refreshed = db.execute(select(User).where(User.username == "legacy_user")).scalar_one()
        assert refreshed.password_hash.startswith(f"{PASSWORD_ALGORITHM}$")
