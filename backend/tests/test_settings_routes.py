from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import settings


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


if __name__ == "__main__":
    unittest.main()
