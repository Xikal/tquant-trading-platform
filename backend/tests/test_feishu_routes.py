from __future__ import annotations

import os
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import feishu
from app.core.config import get_settings
from app.core.database import get_db
from app.models.base import Base


class FeishuRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_token = os.environ.get("FEISHU_VERIFICATION_TOKEN")
        os.environ["FEISHU_VERIFICATION_TOKEN"] = "verify-token"
        get_settings.cache_clear()
        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, future=True)
        app = FastAPI()
        app.include_router(feishu.router, prefix="/api")
        app.dependency_overrides[get_db] = self._override_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        if self.original_token is None:
            os.environ.pop("FEISHU_VERIFICATION_TOKEN", None)
        else:
            os.environ["FEISHU_VERIFICATION_TOKEN"] = self.original_token
        get_settings.cache_clear()

    def test_url_verification_requires_matching_token(self) -> None:
        response = self.client.post(
            "/api/feishu/event",
            json={"type": "url_verification", "token": "verify-token", "challenge": "abc"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["challenge"], "abc")

    def test_url_verification_rejects_invalid_token(self) -> None:
        response = self.client.post(
            "/api/feishu/event",
            json={"type": "url_verification", "token": "bad", "challenge": "abc"},
        )
        self.assertEqual(response.status_code, 403)

    def test_unbound_user_gets_binding_prompt(self) -> None:
        response = self.client.post(
            "/api/feishu/event",
            json={
                "header": {"token": "verify-token"},
                "event": {
                    "sender": {"sender_id": {"open_id": "ou_test"}},
                    "message": {"content": "{\"text\":\"持仓\"}"},
                },
            },
        )
        self.assertEqual(response.status_code, 200)
        text = response.json()["response"]["content"]["text"]
        self.assertIn("需要绑定账户", text)

    def _override_db(self):
        db = self.Session()
        try:
            yield db
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
