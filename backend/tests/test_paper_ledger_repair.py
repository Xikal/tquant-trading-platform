from __future__ import annotations

import unittest
from os import environ

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import auth, paper
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import clear_rate_limit_events
from app.models.base import Base
from app.models.entities import PaperAccount, PaperOrder, PaperTrade, User
from app.services.paper.ledger_repair import PaperLedgerRepairService
from app.services.paper.stock_pnl import PaperStockPnlService


class PaperLedgerRepairTests(unittest.TestCase):
    def setUp(self) -> None:
        self._auth_secret_original = environ.get("AUTH_SECRET_KEY")
        self._admin_token_original = environ.get("ADMIN_API_TOKEN")
        self._mfa_requirement_original = environ.get("AUTH_REQUIRE_MFA_FOR_PAPER_TRADE")
        environ["AUTH_SECRET_KEY"] = "test-auth-secret"
        environ["ADMIN_API_TOKEN"] = "test-admin-token"
        environ["AUTH_REQUIRE_MFA_FOR_PAPER_TRADE"] = "false"
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
        self._restore_env("AUTH_SECRET_KEY", self._auth_secret_original)
        self._restore_env("ADMIN_API_TOKEN", self._admin_token_original)
        self._restore_env("AUTH_REQUIRE_MFA_FOR_PAPER_TRADE", self._mfa_requirement_original)
        get_settings.cache_clear()

    def test_service_rebuilds_account_after_invalid_oversell(self) -> None:
        with self.Session() as db:
            account = self._seed_invalid_account(db)
            service = PaperLedgerRepairService(db)
            preview = service.preview(account.id)
            self.assertEqual(preview.issue_count, 2)
            self.assertGreater(float(preview.reconciliation_gap_before), 0)

            applied = service.apply(account.id)
            db.commit()
            self.assertTrue(applied.applied)
            self.assertEqual(applied.issue_count, 2)
            self.assertAlmostEqual(float(applied.reconciliation_gap_after), 0.0, places=2)

            refreshed = db.get(PaperAccount, account.id)
            pnl = PaperStockPnlService(db).summary(account.id)
            self.assertAlmostEqual(float(refreshed.total_assets), float(applied.corrected_total_assets), places=2)
            self.assertAlmostEqual(pnl["summary"]["reconciliation_gap"], 0.0, places=2)
            self.assertEqual(
                db.execute(select(PaperTrade).where(PaperTrade.account_id == account.id)).scalars().all()[1].quantity,
                100,
            )

    def test_admin_route_can_preview_and_apply_repair(self) -> None:
        headers = self._register("paper_repair_admin")
        with self.Session() as db:
            user = db.execute(select(User).where(User.username == "paper_repair_admin")).scalar_one()
            user.roles = "admin"
            account = self._seed_invalid_account(db, user_id=user.id)
            account_id = account.id
            db.commit()

        preview = self.client.post(
            "/api/paper/account/reconcile",
            headers={**headers, "X-Admin-Token": "test-admin-token"},
            json={"account_id": account_id, "apply": False},
        )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()["issue_count"], 2)

        applied = self.client.post(
            "/api/paper/account/reconcile",
            headers={**headers, "X-Admin-Token": "test-admin-token"},
            json={"account_id": account_id, "apply": True},
        )
        self.assertEqual(applied.status_code, 200)
        self.assertTrue(applied.json()["applied"])
        self.assertAlmostEqual(applied.json()["reconciliation_gap_after"], 0.0, places=2)

    def _register(self, username: str) -> dict[str, str]:
        response = self.client.post("/api/auth/register", json={"username": username, "password": "secret123"})
        self.assertEqual(response.status_code, 200)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def _seed_invalid_account(self, db, user_id: int | None = None) -> PaperAccount:
        account = PaperAccount(
            user_id=user_id,
            name="测试异常账户",
            initial_cash=100000,
            cash_available=110000,
            total_assets=110000,
            realized_pnl=10000,
            status="active",
        )
        db.add(account)
        db.flush()
        self._add_order_trade(
            db,
            account_id=account.id,
            symbol="000001",
            side="buy",
            quantity=100,
            price=10.0,
            gross_amount=1000.0,
            net_amount=1005.0,
            reason="测试买入",
        )
        self._add_order_trade(
            db,
            account_id=account.id,
            symbol="000001",
            side="sell",
            quantity=200,
            price=11.0,
            gross_amount=2200.0,
            net_amount=2193.0,
            reason="异常超卖",
        )
        self._add_order_trade(
            db,
            account_id=account.id,
            symbol="000002",
            side="sell",
            quantity=100,
            price=5.0,
            gross_amount=500.0,
            net_amount=495.0,
            reason="无持仓卖出",
        )
        db.commit()
        db.refresh(account)
        return account

    def _add_order_trade(
        self,
        db,
        *,
        account_id: int,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        gross_amount: float,
        net_amount: float,
        reason: str,
    ) -> None:
        order = PaperOrder(
            account_id=account_id,
            symbol=symbol,
            name=symbol,
            side=side,
            order_type="market",
            quantity=quantity,
            filled_quantity=quantity,
            avg_fill_price=price,
            status="filled",
            reason=reason,
            strategy_key="first_board",
        )
        db.add(order)
        db.flush()
        db.add(
            PaperTrade(
                order_id=order.id,
                account_id=account_id,
                symbol=symbol,
                side=side,
                price=price,
                quantity=quantity,
                gross_amount=gross_amount,
                commission=5.0,
                stamp_tax=0.0,
                transfer_fee=0.0,
                net_amount=net_amount,
                strategy_key="first_board",
                entry_reason=reason if side == "buy" else "",
                exit_reason=reason if side == "sell" else "",
            )
        )

    def _restore_env(self, key: str, value: str | None) -> None:
        if value is None:
            environ.pop(key, None)
        else:
            environ[key] = value


if __name__ == "__main__":
    unittest.main()
