from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import settings
from app.core.admin_auth import require_admin_auth
from app.core.auth import get_current_user
from app.core.database import get_db


class SettingsRouteSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(settings.router, prefix="/api")
        self.client = TestClient(app)

    def test_settings_requires_login(self) -> None:
        response = self.client.get("/api/settings")
        self.assertEqual(response.status_code, 401)

    def test_runtime_settings_requires_login(self) -> None:
        response = self.client.get("/api/settings/runtime")
        self.assertEqual(response.status_code, 401)

    def test_main_force_model_settings_requires_login(self) -> None:
        response = self.client.get("/api/settings/main-force-model")
        self.assertEqual(response.status_code, 401)

    def test_main_force_model_settings_is_admin_readonly(self) -> None:
        app = FastAPI()
        app.include_router(settings.router, prefix="/api")
        app.dependency_overrides[get_current_user] = lambda: object()
        app.dependency_overrides[require_admin_auth] = lambda: None
        app.dependency_overrides[get_db] = lambda: object()
        with patch.object(
            settings,
            "summarize_main_force_shadow",
            return_value={
                "model_key": "main_force_accumulation_washout_markup_v1",
                "promotion_ready": False,
            },
        ):
            response = TestClient(app).get("/api/settings/main-force-model")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["config"]["main_force_model_ranking_enabled"])
        self.assertFalse(payload["config"]["main_force_model_paper_suggestion_enabled"])
        self.assertEqual(payload["policy"]["settings_write_api"], "not_exposed")


if __name__ == "__main__":
    unittest.main()
