from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import strategy_meta
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.schema_defs.strategy_meta import (
    StrategyMetaOut,
    StrategyMetaResponse,
    StrategyPresetOut,
    StrategyPresetResponse,
    SymbolSearchItem,
    SymbolSearchResponse,
)


def _override_user():
    class UserStub:
        id = 1
        username = "tester"
        is_active = True

    return UserStub()


def _override_db():
    yield object()


class _StrategyMetadataServiceStub:
    def __init__(self, db):  # noqa: ANN001
        self.db = db

    def list_strategy_meta(self) -> StrategyMetaResponse:
        return StrategyMetaResponse(
            strategies=[
                StrategyMetaOut(
                    key="first_board",
                    name="首板回调",
                    display_name="首板回调",
                    description="首板回调策略",
                    category="生产策略",
                    risk_level="medium",
                    typical_holding_days="1-3天",
                    sort_order=10,
                )
            ]
        )

    def list_presets(self) -> StrategyPresetResponse:
        return StrategyPresetResponse(
            presets=[
                StrategyPresetOut(
                    id=None,
                    key="quick_check",
                    name="快速体检",
                    description="快速回测预设",
                    config={"range": "6m", "strategies": ["first_board"]},
                    sort_order=10,
                )
            ]
        )

    def search_symbols(self, query: str, limit: int = 10) -> SymbolSearchResponse:
        return SymbolSearchResponse(
            items=[
                SymbolSearchItem(
                    symbol="510300",
                    name="沪深300ETF",
                    latest_price=3.512,
                    industry="ETF",
                    market="SH",
                    instrument_type="etf",
                )
            ][:limit],
            total=1 if query else 0,
        )


class StrategyMetaRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_service = strategy_meta.StrategyMetadataService
        strategy_meta.StrategyMetadataService = _StrategyMetadataServiceStub
        app = FastAPI()
        app.include_router(strategy_meta.router, prefix="/api")
        app.dependency_overrides[get_current_user] = _override_user
        app.dependency_overrides[get_db] = _override_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        strategy_meta.StrategyMetadataService = self.original_service

    def test_strategy_meta_returns_compact_strategy_list(self) -> None:
        response = self.client.get("/api/strategies/meta")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["strategies"][0]["key"], "first_board")

    def test_strategy_presets_return_quick_configs(self) -> None:
        response = self.client.get("/api/strategy/presets")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["presets"][0]["key"], "quick_check")

    def test_symbol_search_returns_agent_friendly_shape(self) -> None:
        response = self.client.get("/api/symbols/search?q=510300&limit=5")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["items"][0]["symbol"], "510300")
        self.assertEqual(body["items"][0]["latest_price"], 3.512)


if __name__ == "__main__":
    unittest.main()
