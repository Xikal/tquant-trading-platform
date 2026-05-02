from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import auth, paper
from app.core.database import get_db
from app.models.base import Base
from app.models.entities import User


class PaperRouteTests(unittest.TestCase):
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
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "rejected")
        self.assertIn("100 股整数倍", response.json()["reject_reason"])

    def test_paused_account_rejects_order(self) -> None:
        headers = self._register("paper_paused")
        pause = self.client.post("/api/paper/account/pause", headers=headers)
        self.assertEqual(pause.status_code, 200)

        response = self._paper_order(headers, quantity=100)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "rejected")
        self.assertIn("账户已暂停", response.json()["reject_reason"])

    def test_large_single_order_is_blocked_by_risk_control(self) -> None:
        headers = self._register("paper_risk")
        response = self._paper_order(headers, quantity=8000)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "rejected")
        self.assertIn("单笔买入金额超过账户资产 30%", response.json()["reject_reason"])

    def test_same_day_sell_rejected_by_t1_rule(self) -> None:
        headers = self._register("paper_t1")
        buy = self._paper_order(headers, quantity=100)
        self.assertEqual(buy.status_code, 200)
        self.assertEqual(buy.json()["status"], "filled")

        sell = self._paper_order(headers, side="sell", quantity=100)
        self.assertEqual(sell.status_code, 200)
        self.assertEqual(sell.json()["status"], "rejected")
        self.assertIn("当日买入未解锁", sell.json()["reject_reason"])

    def test_risk_status_requires_login_and_returns_limits(self) -> None:
        self.assertEqual(self.client.get("/api/paper/risk").status_code, 401)
        headers = self._register("paper_risk_status")
        response = self.client.get("/api/paper/risk", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["max_single_order_pct"], 30.0)
        self.assertEqual(response.json()["max_daily_order_count"], 20)

    def _register(self, username: str) -> dict[str, str]:
        response = self.client.post(
            "/api/auth/register",
            json={"username": username, "password": "secret123"},
        )
        self.assertEqual(response.status_code, 200)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def _paper_order(self, headers: dict[str, str], *, side: str = "buy", quantity: int = 100):
        return self.client.post(
            "/api/paper/orders",
            headers=headers,
            json={
                "symbol": "510300",
                "name": "沪深300ETF",
                "side": side,
                "order_type": "market",
                "quantity": quantity,
                "current_price": 4.0,
            },
        )


if __name__ == "__main__":
    unittest.main()
