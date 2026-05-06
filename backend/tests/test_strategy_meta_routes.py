from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import strategy_meta
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.base import Base
from app.models.entities import LowBuyResultSnapshot, LowBuyScanSnapshot
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
                    tier="core",
                    category_key="core",
                    category="生产策略",
                    display_category="生产策略",
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
        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, future=True)
        app = FastAPI()
        app.include_router(strategy_meta.router, prefix="/api")
        app.dependency_overrides[get_current_user] = _override_user

        def override_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        strategy_meta.StrategyMetadataService = self.original_service

    def test_strategy_meta_returns_compact_strategy_list(self) -> None:
        response = self.client.get("/api/strategies/meta")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["strategies"][0]["key"], "first_board")
        self.assertEqual(body["strategies"][0]["tier"], "core")
        self.assertEqual(body["strategies"][0]["category_key"], "core")
        self.assertEqual(body["strategies"][0]["display_category"], "生产策略")

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

    def test_signal_replay_uses_recent_scan_date_window(self) -> None:
        with self.Session() as db:
            db.add_all(
                [
                    LowBuyScanSnapshot(latest_trade_date="2026-04-28", strategy_key="first_board"),
                    LowBuyScanSnapshot(latest_trade_date="2026-04-29", strategy_key="first_board"),
                    LowBuyResultSnapshot(
                        latest_trade_date="2026-04-27",
                        strategy_key="first_board",
                        symbol="000001",
                        name="旧样本",
                        score=99,
                        buy_signal_state="buy_now",
                        payload_json='{"summary":"old"}',
                    ),
                    LowBuyResultSnapshot(
                        latest_trade_date="2026-04-28",
                        strategy_key="first_board",
                        symbol="000002",
                        name="新样本A",
                        score=80,
                        buy_signal_state="near_entry",
                        payload_json='{"entry_low":10,"entry_high":11,"reasons":["接近买点"]}',
                    ),
                    LowBuyResultSnapshot(
                        latest_trade_date="2026-04-29",
                        strategy_key="first_board",
                        symbol="000003",
                        name="新样本B",
                        score=70,
                        buy_signal_state="buy_now",
                        payload_json='{"latest_price":12.3,"change_pct":1.2}',
                    ),
                ]
            )
            db.commit()

        response = self.client.get("/api/strategy/signals/replay?strategy=first_board&lookback_days=2&limit=10")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 2)
        self.assertEqual([item["symbol"] for item in body["items"]], ["000003", "000002"])

    def test_signal_replay_keyword_filters_recent_rows(self) -> None:
        with self.Session() as db:
            db.add(LowBuyScanSnapshot(latest_trade_date="2026-04-29", strategy_key="first_board"))
            db.add_all(
                [
                    LowBuyResultSnapshot(
                        latest_trade_date="2026-04-29",
                        strategy_key="first_board",
                        symbol="002859",
                        name="洁美科技",
                        score=95,
                        buy_signal_state="buy_now",
                        payload_json='{"summary":"价格进入买点区"}',
                    ),
                    LowBuyResultSnapshot(
                        latest_trade_date="2026-04-29",
                        strategy_key="first_board",
                        symbol="510300",
                        name="沪深300ETF",
                        score=60,
                        buy_signal_state="watch",
                        payload_json="{}",
                    ),
                ]
            )
            db.commit()

        response = self.client.get("/api/strategy/signals/replay?strategy=first_board&symbol=洁美&limit=10")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["items"][0]["symbol"], "002859")


if __name__ == "__main__":
    unittest.main()
