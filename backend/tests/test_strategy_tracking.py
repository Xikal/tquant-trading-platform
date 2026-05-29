from __future__ import annotations

import json
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import strategy_tracking
from app.core.admin_auth import require_admin_auth
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.base import Base
from app.models.entities import DailyBarSnapshot, LowBuyResultSnapshot, LowBuyTradeLifecycleSnapshot, StrategyMetadata


def _override_user():
    class UserStub:
        id = 1
        username = "tester"
        is_active = True

    return UserStub()


class StrategyTrackingTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, future=True)
        app = FastAPI()
        app.include_router(strategy_tracking.router, prefix="/api")
        app.dependency_overrides[get_current_user] = _override_user
        app.dependency_overrides[require_admin_auth] = lambda: None

        def override_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def test_items_filter_production_strategy_and_isolate_signal_day(self) -> None:
        self._seed_tracking_fixture()

        response = self.client.get("/api/strategy-tracking/items?range=10&limit=10")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 1)
        item = body["items"][0]
        self.assertEqual(item["strategy_key"], "first_board")
        self.assertEqual(item["first_signal_date"], "2026-04-20")
        self.assertTrue(item["entry_touched"])
        self.assertTrue(item["stop_triggered"])
        self.assertEqual(item["stop_triggered_date"], "2026-04-22")
        self.assertEqual(item["max_gain_pct"], 10.0)
        self.assertEqual(item["max_drawdown_pct"], -16.19)
        self.assertEqual(item["lifecycle_status"], "stopped")
        self.assertFalse(body["production_writeable"])
        self.assertTrue(body["rust_math_used"])

    def test_detail_is_lazy_and_returns_compact_snapshot(self) -> None:
        self._seed_tracking_fixture()

        item_id = "first_board:600000:2026-04-20"
        response = self.client.get(f"/api/strategy-tracking/items/{item_id}")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["item"]["id"], item_id)
        self.assertEqual([point["trade_date"] for point in body["timeline"]], ["2026-04-21", "2026-04-22"])
        self.assertEqual({marker["kind"] for marker in body["markers"]}, {"first_signal", "target", "stop", "highest"})
        self.assertNotIn("payload_json", body["signal_snapshot"])
        self.assertIn("summary_reason", body["signal_snapshot"])

    def test_bad_payload_and_missing_bars_degrade_without_blocking_other_items(self) -> None:
        with self.Session() as db:
            self._seed_metadata(db)
            db.add(
                LowBuyResultSnapshot(
                    latest_trade_date="2026-04-20",
                    strategy_key="first_board",
                    symbol="600001",
                    name="坏数据",
                    score=88,
                    buy_signal_state="buy_now",
                    payload_json="{bad-json",
                )
            )
            db.commit()

        response = self.client.get("/api/strategy-tracking/items?range=10&limit=10")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["items"][0]["data_quality"], "partial")
        self.assertEqual(body["items"][0]["lifecycle_status"], "data_unavailable")
        self.assertIn("payload_json_invalid", body["partial_errors"][0])

    def test_limit_above_50_is_rejected_by_route(self) -> None:
        response = self.client.get("/api/strategy-tracking/items?limit=80")

        self.assertEqual(response.status_code, 422)

    def test_refresh_is_read_through_and_does_not_mutate_strategy_outputs(self) -> None:
        self._seed_tracking_fixture()
        with self.Session() as db:
            before = db.query(LowBuyResultSnapshot).count()

        response = self.client.post("/api/strategy-tracking/refresh?range=10", headers={"X-Admin-Token": "test-admin-token"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["storage_mode"], "read_through_view_no_strategy_write")
        self.assertFalse(body["changed_strategy_results"])
        self.assertFalse(body["changed_paper_ledger"])
        with self.Session() as db:
            after = db.query(LowBuyResultSnapshot).count()
        self.assertEqual(after, before)

    def _seed_tracking_fixture(self) -> None:
        with self.Session() as db:
            self._seed_metadata(db)
            db.add_all(
                [
                    LowBuyResultSnapshot(
                        latest_trade_date="2026-04-20",
                        strategy_key="first_board",
                        symbol="600000",
                        name="浦发银行",
                        score=90,
                        buy_signal_state="near_entry",
                        payload_json=json.dumps(_payload(price=10.0), ensure_ascii=False),
                    ),
                    LowBuyResultSnapshot(
                        latest_trade_date="2026-04-21",
                        strategy_key="first_board",
                        symbol="600000",
                        name="浦发银行",
                        score=95,
                        buy_signal_state="buy_now",
                        payload_json=json.dumps(_payload(price=10.2), ensure_ascii=False),
                    ),
                    LowBuyResultSnapshot(
                        latest_trade_date="2026-04-21",
                        strategy_key="classic_retrace",
                        symbol="600002",
                        name="研究策略样本",
                        score=99,
                        buy_signal_state="buy_now",
                        payload_json=json.dumps(_payload(price=10.0), ensure_ascii=False),
                    ),
                    LowBuyTradeLifecycleSnapshot(
                        signal_trade_date="2026-04-20",
                        strategy_key="first_board",
                        symbol="600000",
                        name="浦发银行",
                        signal_state="buy_now",
                        status="planned",
                        entry_plan_low=9.5,
                        entry_plan_high=10.5,
                        stop_loss=9.0,
                        take_profit=11.0,
                    ),
                    _bar("600000", "2026-04-20", high=20.0, low=8.0, close=10.0),
                    _bar("600000", "2026-04-21", high=11.0, low=9.6, close=10.5),
                    _bar("600000", "2026-04-22", high=10.4, low=8.8, close=8.8),
                    _bar("600002", "2026-04-21", high=11.0, low=9.5, close=10.5),
                ]
            )
            db.commit()

    def _seed_metadata(self, db) -> None:  # noqa: ANN001
        db.add_all(
            [
                StrategyMetadata(
                    key="first_board",
                    display_name="首板回调",
                    category="core",
                    enabled=True,
                    visibility="full",
                ),
                StrategyMetadata(
                    key="classic_retrace",
                    display_name="经典回踩",
                    category="research",
                    enabled=True,
                    visibility="full",
                ),
            ]
        )


def _payload(price: float) -> dict[str, object]:
    return {
        "strategy_title": "首板回调",
        "latest_price": price,
        "entry_zone_low": 9.5,
        "entry_zone_high": 10.5,
        "stop_loss": 9.0,
        "take_profit": 11.0,
        "summary_reason": "缩量回踩到支撑位",
        "reasons": ["回踩支撑"],
        "risks": ["跌破止损"],
        "data_quality": "ok",
    }


def _bar(symbol: str, trade_date: str, *, high: float, low: float, close: float) -> DailyBarSnapshot:
    return DailyBarSnapshot(
        symbol=symbol,
        market="CN",
        instrument_type="stock",
        trade_date=trade_date,
        open_price=10.0,
        close_price=close,
        high_price=high,
        low_price=low,
        volume=1000,
        amount=10000,
        pct_chg=0.0,
        source="unit-test",
        data_quality="ok",
    )


if __name__ == "__main__":
    unittest.main()
