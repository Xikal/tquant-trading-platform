from __future__ import annotations

import unittest
from os import environ

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import auth, screeners, v1
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import clear_rate_limit_events
from app.models.base import Base


class StrategyGovernanceRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self._auth_secret_original = environ.get("AUTH_SECRET_KEY")
        self._admin_token_original = environ.get("ADMIN_API_TOKEN")
        environ["AUTH_SECRET_KEY"] = "test-auth-secret"
        environ["ADMIN_API_TOKEN"] = "test-admin-token"
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
        app.include_router(screeners.router, prefix="/api")
        app.include_router(v1.router, prefix="/api")

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
        if self._admin_token_original is None:
            environ.pop("ADMIN_API_TOKEN", None)
        else:
            environ["ADMIN_API_TOKEN"] = self._admin_token_original
        get_settings.cache_clear()

    def test_strategy_governance_requires_login(self) -> None:
        response = self.client.get("/api/screeners/low-buy/strategies")
        self.assertEqual(response.status_code, 401)

    def test_strategy_governance_exposes_tiers_and_default(self) -> None:
        headers = self._register("strategy_governance")
        response = self.client.get("/api/screeners/low-buy/strategies", headers=headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["default_strategy"], "first_board")
        by_key = {item["strategy_key"]: item for item in payload["items"]}
        self.assertEqual(by_key["first_board"]["tier"], "core")
        self.assertEqual(by_key["classic_retrace"]["status"], "research")
        self.assertTrue(by_key["late_session_strong_support"]["requires_mainline_industry"])
        self.assertEqual(by_key["mainline_limitup_shrink_retrace_reclaim"]["status"], "watch")
        self.assertIn("真实成交样本不足", by_key["mainline_limitup_shrink_retrace_reclaim"]["status_text"])
        self.assertIn("strategy_health_score", by_key["first_board"])
        self.assertIn("strategy_health_text", by_key["first_board"])
        self.assertIn("performance_sample_count", by_key["first_board"])

    def test_v1_strategy_governance_and_agent_tools(self) -> None:
        headers = self._register("strategy_v1")
        strategies = self.client.get("/api/v1/strategy/low-buy/strategies", headers=headers)
        tools = self.client.get("/api/v1/agent/tools", headers=headers)
        self.assertEqual(strategies.status_code, 200)
        self.assertEqual(tools.status_code, 200)
        self.assertTrue(any(item["name"] == "get_priority_board" for item in tools.json()["items"]))

    def test_strategy_governance_admin_update(self) -> None:
        headers = self._register("strategy_update")
        response = self.client.patch(
            "/api/screeners/low-buy/strategies/volume_shrink",
            headers={**headers, "X-Admin-Token": "test-admin-token"},
            json={"status": "paused", "reason": "测试暂停"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        by_key = {item["strategy_key"]: item for item in payload["items"]}
        self.assertEqual(by_key["volume_shrink"]["status"], "paused")
        self.assertIn("测试暂停", by_key["volume_shrink"]["auto_governance_reason"])

        restored = self.client.patch(
            "/api/screeners/low-buy/strategies/volume_shrink",
            headers={**headers, "X-Admin-Token": "test-admin-token"},
            json={"status": "active"},
        )
        self.assertEqual(restored.status_code, 200)
        restored_by_key = {item["strategy_key"]: item for item in restored.json()["items"]}
        self.assertNotEqual(restored_by_key["volume_shrink"]["status"], "paused")

    def _register(self, username: str) -> dict[str, str]:
        response = self.client.post(
            "/api/auth/register",
            json={"username": username, "password": "secret123"},
        )
        self.assertEqual(response.status_code, 200)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}


if __name__ == "__main__":
    unittest.main()
