from __future__ import annotations

import unittest
from os import environ
from types import SimpleNamespace

from fastapi import HTTPException

from app.core.admin_auth import require_admin_auth
from app.core.config import get_settings
from app.services.feishu.feishu_app import FeishuAppConfig
from app.services.market.intraday import MarketIntradayMixin
from app.services.market.shared import DataSourceError


class SecurityHardeningTests(unittest.TestCase):
    def tearDown(self) -> None:
        for key in ("FEISHU_VERIFICATION_TOKEN", "ADMIN_API_TOKEN"):
            environ.pop(key, None)
        get_settings.cache_clear()

    def test_feishu_empty_verification_token_rejects_events(self) -> None:
        environ["FEISHU_VERIFICATION_TOKEN"] = ""
        get_settings.cache_clear()

        self.assertFalse(FeishuAppConfig().verify_token(""))
        self.assertFalse(FeishuAppConfig().verify_token("any-token"))

    def test_admin_auth_missing_token_returns_service_unavailable(self) -> None:
        environ["ADMIN_API_TOKEN"] = ""
        get_settings.cache_clear()

        with self.assertRaises(HTTPException) as ctx:
            require_admin_auth(SimpleNamespace(), x_admin_token=None, authorization=None)

        self.assertEqual(ctx.exception.status_code, 503)

    def test_admin_token_env_is_loaded_by_settings(self) -> None:
        environ["ADMIN_API_TOKEN"] = "admin-token-from-env"
        get_settings.cache_clear()

        self.assertEqual(get_settings().admin_api_token, "admin-token-from-env")

    def test_admin_auth_accepts_admin_token_env(self) -> None:
        environ["ADMIN_API_TOKEN"] = "admin-token-from-env"
        get_settings.cache_clear()

        self.assertIsNone(
            require_admin_auth(
                SimpleNamespace(),
                x_admin_token="admin-token-from-env",
                authorization=None,
            )
        )

    def test_intraday_subprocess_rejects_unsafe_symbol(self) -> None:
        class Service(MarketIntradayMixin):
            settings = SimpleNamespace(http_timeout=1)

            @staticmethod
            def _to_sina_symbol(_symbol: str) -> str:
                return "sh000001;rm"

        with self.assertRaises(DataSourceError):
            Service()._fetch_sina_minute_bars_subprocess("000001;rm")


if __name__ == "__main__":
    unittest.main()
