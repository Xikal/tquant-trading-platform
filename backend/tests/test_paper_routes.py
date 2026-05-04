from __future__ import annotations

import unittest
from unittest.mock import patch
from os import environ
from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import auth, paper
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import clear_rate_limit_events
from app.models.base import Base
from app.models.entities import PaperOrder, PaperPosition, PaperPositionLot, PaperTrade, User


class PaperRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self._auth_secret_original = environ.get("AUTH_SECRET_KEY")
        environ["AUTH_SECRET_KEY"] = "test-auth-secret"
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
        app.include_router(paper.router, prefix="/api")

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

    def test_paper_routes_require_login(self) -> None:
        response = self.client.get("/api/paper/account")
        self.assertEqual(response.status_code, 401)

    def test_paper_accounts_are_user_isolated(self) -> None:
        user_a = self._register("paper_a")
        user_b = self._register("paper_b")

        buy = self.client.post(
            "/api/paper/orders",
            headers=user_a,
            json={
                "symbol": "510300",
                "name": "沪深300ETF",
                "side": "buy",
                "order_type": "market",
                "quantity": 100,
                "current_price": 4.0,
            },
        )
        self.assertEqual(buy.status_code, 200)
        self.assertEqual(buy.json()["status"], "filled")

        positions_a = self.client.get("/api/paper/positions", headers=user_a)
        positions_b = self.client.get("/api/paper/positions", headers=user_b)
        self.assertEqual(positions_a.status_code, 200)
        self.assertEqual(positions_b.status_code, 200)
        self.assertEqual(len(positions_a.json()["positions"]), 1)
        self.assertEqual(len(positions_b.json()["positions"]), 0)

    def test_paper_routes_require_whitelist_permission(self) -> None:
        headers = self._register("paper_blocked")
        with self.Session() as db:
            user = db.execute(select(User).where(User.username == "paper_blocked")).scalar_one()
            user.can_paper_trade = False
            db.commit()

        response = self.client.get("/api/paper/account", headers=headers)
        self.assertEqual(response.status_code, 403)
        self.assertIn("模拟盘权限", response.json()["detail"])

    def test_order_rejects_non_lot_quantity(self) -> None:
        headers = self._register("paper_lot")
        response = self._paper_order(headers, quantity=150)
        self.assertEqual(response.status_code, 400)
        self.assertIn("100 股整数倍", response.json()["detail"])

    def test_paused_account_rejects_order(self) -> None:
        headers = self._register("paper_paused")
        pause = self.client.post("/api/paper/account/pause", headers=headers)
        self.assertEqual(pause.status_code, 200)

        response = self._paper_order(headers, quantity=100)
        self.assertEqual(response.status_code, 400)
        self.assertIn("账户已暂停", response.json()["detail"])

    def test_large_single_order_is_blocked_by_risk_control(self) -> None:
        headers = self._register("paper_risk")
        response = self._paper_order(headers, quantity=8000)
        self.assertEqual(response.status_code, 400)
        self.assertIn("单笔买入金额超过账户资产 30%", response.json()["detail"])

    def test_same_day_sell_rejected_by_t1_rule(self) -> None:
        headers = self._register("paper_t1")
        buy = self._paper_order(headers, symbol="300059", name="东方财富", quantity=100)
        self.assertEqual(buy.status_code, 200)
        self.assertEqual(buy.json()["status"], "filled")

        sell = self._paper_order(headers, symbol="300059", name="东方财富", side="sell", quantity=100)
        self.assertEqual(sell.status_code, 400)
        self.assertIn("当日买入未解锁", sell.json()["detail"])

    def test_etf_same_day_sell_allowed_by_t0_rule(self) -> None:
        headers = self._register("paper_etf_t0")
        buy = self._paper_order(headers, symbol="510300", name="沪深300ETF", quantity=100)
        self.assertEqual(buy.status_code, 200)
        self.assertEqual(buy.json()["status"], "filled")

        sell = self._paper_order(headers, symbol="510300", name="沪深300ETF", side="sell", quantity=100)
        self.assertEqual(sell.status_code, 200)
        self.assertEqual(sell.json()["status"], "filled")

    def test_buy_order_creates_trade_lot_and_sellable_etf_position(self) -> None:
        headers = self._register("paper_buy_lifecycle")
        response = self._paper_order(headers, symbol="510300", name="沪深300ETF", quantity=200, reason="自动回归买入")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "filled")
        self.assertEqual(body["filled_quantity"], 200)

        positions = self.client.get("/api/paper/positions", headers=headers)
        self.assertEqual(positions.status_code, 200)
        self.assertEqual(len(positions.json()["positions"]), 1)
        self.assertEqual(positions.json()["positions"][0]["quantity"], 200)
        self.assertEqual(positions.json()["positions"][0]["available_quantity"], 200)

        trades = self.client.get("/api/paper/trades", headers=headers)
        self.assertEqual(trades.status_code, 200)
        self.assertEqual(len(trades.json()["trades"]), 1)
        self.assertEqual(trades.json()["trades"][0]["entry_reason"], "自动回归买入")

        with self.Session() as db:
            order_count = db.execute(select(PaperOrder)).scalars().all()
            trade_count = db.execute(select(PaperTrade)).scalars().all()
            lot = db.execute(select(PaperPositionLot)).scalar_one()
            self.assertEqual(len(order_count), 1)
            self.assertEqual(len(trade_count), 1)
            self.assertEqual(lot.quantity, 200)
            self.assertEqual(lot.remaining, 200)

    def test_etf_round_trip_closes_position_and_records_sell_trade(self) -> None:
        headers = self._register("paper_round_trip")
        buy = self._paper_order(headers, symbol="510300", name="沪深300ETF", quantity=100, current_price=4.0)
        self.assertEqual(buy.status_code, 200)

        sell = self._paper_order(
            headers,
            symbol="510300",
            name="沪深300ETF",
            side="sell",
            quantity=100,
            current_price=4.2,
            reason="止盈回归",
        )
        self.assertEqual(sell.status_code, 200)
        self.assertEqual(sell.json()["side"], "sell")

        positions = self.client.get("/api/paper/positions", headers=headers)
        self.assertEqual(positions.status_code, 200)
        self.assertEqual(positions.json()["positions"], [])

        with self.Session() as db:
            orders = db.execute(select(PaperOrder).order_by(PaperOrder.id.asc())).scalars().all()
            trades = db.execute(select(PaperTrade).order_by(PaperTrade.id.asc())).scalars().all()
            position = db.execute(select(PaperPosition)).scalar_one()
            lot = db.execute(select(PaperPositionLot)).scalar_one()
            self.assertEqual([order.side for order in orders], ["buy", "sell"])
            self.assertEqual([trade.side for trade in trades], ["buy", "sell"])
            self.assertEqual(trades[-1].exit_reason, "止盈退出")
            self.assertEqual(position.quantity, 0)
            self.assertEqual(position.available_quantity, 0)
            self.assertEqual(lot.remaining, 0)

    def test_stock_buy_keeps_position_unsellable_until_t1_unlock(self) -> None:
        headers = self._register("paper_stock_t1_available")
        buy = self._paper_order(headers, symbol="300059", name="东方财富", quantity=100)
        self.assertEqual(buy.status_code, 200)

        positions = self.client.get("/api/paper/positions", headers=headers)
        self.assertEqual(positions.status_code, 200)
        self.assertEqual(positions.json()["positions"][0]["quantity"], 100)
        self.assertEqual(positions.json()["positions"][0]["available_quantity"], 0)

        with self.Session() as db:
            lot = db.execute(select(PaperPositionLot)).scalar_one()
            self.assertGreater(lot.available_date, date.today())

    def test_trade_tags_can_be_added_and_removed(self) -> None:
        headers = self._register("paper_tags")
        buy = self._paper_order(headers, quantity=100, reason="回踩承接测试")
        self.assertEqual(buy.status_code, 200)

        trades = self.client.get("/api/paper/trades", headers=headers)
        self.assertEqual(trades.status_code, 200)
        trade_id = trades.json()["trades"][0]["id"]
        self.assertEqual(trades.json()["trades"][0]["entry_reason"], "回踩承接测试")

        created = self.client.post(
            f"/api/paper/trades/{trade_id}/tags",
            headers=headers,
            json={"tag": "回踩承接", "note": "测试标签"},
        )
        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["tag"], "回踩承接")

        listed = self.client.get(f"/api/paper/trades/{trade_id}/tags", headers=headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()), 1)

        tag_id = created.json()["id"]
        deleted = self.client.delete(f"/api/paper/trades/{trade_id}/tags/{tag_id}", headers=headers)
        self.assertEqual(deleted.status_code, 200)

    def test_risk_status_requires_login_and_returns_limits(self) -> None:
        self.assertEqual(self.client.get("/api/paper/risk").status_code, 401)
        headers = self._register("paper_risk_status")
        response = self.client.get("/api/paper/risk", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["max_single_order_pct"], 30.0)
        self.assertEqual(response.json()["max_daily_order_count"], 20)

    def test_auto_trading_status_requires_login(self) -> None:
        self.assertEqual(self.client.get("/api/paper/auto-trading/status").status_code, 401)
        headers = self._register("paper_auto_status")
        response = self.client.get("/api/paper/auto-trading/status", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["running"])

    def test_auto_trading_dry_run_uses_user_account(self) -> None:
        headers = self._register("paper_auto_dry_run")
        with patch("app.services.paper.scheduler.PaperAutoTrader.run_once_for_preview") as preview:
            preview.return_value = {"summary": "通过 0 条，过滤 0 条", "will_buy": [], "filtered": []}
            response = self.client.post("/api/paper/auto-trading/dry-run?limit=20", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["summary"], "通过 0 条，过滤 0 条")
        self.assertIsNotNone(preview.call_args.kwargs["account_id"])

    def _register(self, username: str) -> dict[str, str]:
        response = self.client.post(
            "/api/auth/register",
            json={"username": username, "password": "secret123"},
        )
        self.assertEqual(response.status_code, 200)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def _paper_order(
        self,
        headers: dict[str, str],
        *,
        symbol: str = "510300",
        name: str = "沪深300ETF",
        side: str = "buy",
        quantity: int = 100,
        current_price: float = 4.0,
        reason: str = "测试委托",
    ):
        return self.client.post(
            "/api/paper/orders",
            headers=headers,
            json={
                "symbol": symbol,
                "name": name,
                "side": side,
                "order_type": "market",
                "quantity": quantity,
                "current_price": current_price,
                "reason": reason,
            },
        )


if __name__ == "__main__":
    unittest.main()
