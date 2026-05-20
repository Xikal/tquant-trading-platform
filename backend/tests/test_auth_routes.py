from __future__ import annotations

import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from os import environ

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import auth
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import clear_rate_limit_events
from app.models.base import Base

STRONG_TEST_SECRET = "auth-route-test-secret-0123456789abcdef0123456789abcdef0123456789abcdef"


@contextmanager
def settings_env(key: str, value: str):
    original = environ.get(key)
    environ[key] = value
    get_settings.cache_clear()
    try:
        yield
    finally:
        if original is None:
            environ.pop(key, None)
        else:
            environ[key] = original
        get_settings.cache_clear()


class AuthRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self._auth_secret_original = environ.get("AUTH_SECRET_KEY")
        environ["AUTH_SECRET_KEY"] = STRONG_TEST_SECRET
        get_settings.cache_clear()
        clear_rate_limit_events()
        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, future=True)

        app = FastAPI()
        app.include_router(auth.router, prefix="/api")

        def override_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        if self._auth_secret_original is None:
            environ.pop("AUTH_SECRET_KEY", None)
        else:
            environ["AUTH_SECRET_KEY"] = self._auth_secret_original
        get_settings.cache_clear()

    def test_register_login_me_refresh_logout(self) -> None:
        register = self.client.post(
            "/api/auth/register",
            json={
                "username": "TraderA",
                "password": "secret123",
                "display_name": "交易员A",
                "device_name": "ios",
            },
        )
        self.assertEqual(register.status_code, 200)
        registered = register.json()
        self.assertEqual(registered["user"]["username"], "tradera")
        self.assertTrue(registered["user"]["can_paper_trade"])
        self.assertEqual(registered["user"]["roles"], [])
        self.assertTrue(registered["access_token"])
        self.assertEqual(registered["refresh_token"], "")
        self.assertIn("tquant_refresh_token", register.headers.get("set-cookie", ""))
        claims = jwt.decode(registered["access_token"], options={"verify_signature": False})
        self.assertGreater(int(claims["exp"]), int(datetime.now(timezone.utc).timestamp()))
        self.assertLessEqual(int(claims["iat"]), int(datetime.now(timezone.utc).timestamp()) + 1)
        self.assertEqual(claims["aud"], "tquant-client")
        self.assertEqual(claims["iss"], "tquant")
        self.assertGreater(int(claims["sid"]), 0)
        self.assertEqual(int(claims["tv"]), 0)
        self.assertTrue(claims["jti"])

        me = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {registered['access_token']}"},
        )
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["user"]["display_name"], "交易员A")
        self.assertTrue(me.json()["user"]["can_paper_trade"])

        access = self.client.get(
            "/api/auth/paper-access",
            headers={"Authorization": f"Bearer {registered['access_token']}"},
        )
        self.assertEqual(access.status_code, 200)
        self.assertTrue(access.json()["can_paper_trade"])

        login = self.client.post(
            "/api/auth/login",
            json={"username": "tradera", "password": "secret123"},
        )
        self.assertEqual(login.status_code, 200)
        logged_in = login.json()
        self.assertEqual(logged_in["refresh_token"], "")

        refresh = self.client.post(
            "/api/auth/refresh",
            json={},
        )
        self.assertEqual(refresh.status_code, 200)
        refreshed = refresh.json()
        self.assertEqual(refreshed["refresh_token"], "")
        self.assertIn("tquant_refresh_token", refresh.headers.get("set-cookie", ""))

        repeated_refresh = self.client.post(
            "/api/auth/refresh",
            json={},
        )
        self.assertEqual(repeated_refresh.status_code, 200)
        self.assertTrue(repeated_refresh.json()["access_token"])

        logout = self.client.post(
            "/api/auth/logout",
            json={},
        )
        self.assertEqual(logout.status_code, 200)

        revoked = self.client.post(
            "/api/auth/refresh",
            json={},
        )
        self.assertEqual(revoked.status_code, 401)

        revoked_access = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {refreshed['access_token']}"},
        )
        self.assertEqual(revoked_access.status_code, 401)

    def test_private_route_requires_bearer_token(self) -> None:
        response = self.client.get("/api/auth/me")
        self.assertEqual(response.status_code, 401)

    def test_whitelist_blocks_unlisted_accounts(self) -> None:
        with settings_env("AUTH_ALLOWED_USERNAMES", "allowed_user"):
            blocked = self.client.post(
                "/api/auth/register",
                json={"username": "blocked_user", "password": "secret123"},
            )
            self.assertEqual(blocked.status_code, 401)
            self.assertIn("白名单", blocked.json()["detail"])

            allowed = self.client.post(
                "/api/auth/register",
                json={"username": "Allowed_User", "password": "secret123"},
            )
            self.assertEqual(allowed.status_code, 200)
            self.assertEqual(allowed.json()["user"]["username"], "allowed_user")

    def test_login_rate_limit_is_scoped_by_username(self) -> None:
        for _ in range(5):
            response = self.client.post(
                "/api/auth/login",
                json={"username": "alpha_user", "password": "bad-password"},
            )
            self.assertEqual(response.status_code, 401)

        blocked = self.client.post(
            "/api/auth/login",
            json={"username": "alpha_user", "password": "bad-password"},
        )
        self.assertEqual(blocked.status_code, 429)

        other_user = self.client.post(
            "/api/auth/login",
            json={"username": "beta_user", "password": "bad-password"},
        )
        self.assertEqual(other_user.status_code, 401)


if __name__ == "__main__":
    unittest.main()
