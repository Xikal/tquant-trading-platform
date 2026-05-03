from __future__ import annotations

import unittest
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import market
from app.core.auth import get_current_user


def _override_user():
    class UserStub:
        id = 1
        username = "tester"
        is_active = True

    return UserStub()


class MarketRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_market_data = market.market_data
        market.market_data = SimpleNamespace(get_market_regime_fast=self._regime)
        app = FastAPI()
        app.include_router(market.router, prefix="/api")
        app.dependency_overrides[get_current_user] = _override_user
        self.client = TestClient(app)

    def tearDown(self) -> None:
        market.market_data = self.original_market_data

    def test_market_breadth_returns_compact_payload(self) -> None:
        response = self.client.get("/api/market/breadth")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["state_text"], "震荡修复")
        self.assertEqual(body["hot_industries"], ["半导体"])

    @staticmethod
    def _regime():
        return SimpleNamespace(
            state="repair",
            label="震荡修复",
            breadth_ready=True,
            emotion_ready=True,
            stock_up_ratio=0.58,
            stock_median_change=0.42,
            largecap_change=0.2,
            smallcap_change=0.5,
            style_divergence=0.3,
            limit_up_count=48,
            limit_down_count=2,
            broken_board_ratio=0.16,
            promotion_ratio=0.35,
            board_height=5,
            hot_industries=["半导体"],
            hot_turnover=1.2,
            hot_overlap_ratio=0.6,
        )


if __name__ == "__main__":
    unittest.main()
