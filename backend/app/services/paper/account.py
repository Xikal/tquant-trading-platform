from __future__ import annotations

from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.entities import (
    PaperAccount,
    PaperAgentRun,
    PaperOrder,
    PaperPerformanceSnapshot,
    PaperPosition,
    PaperPositionLot,
    PaperTrade,
)


class PaperAccountService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_account(self, name: str, initial_cash: Decimal, user_id: int | None = None) -> PaperAccount:
        account = PaperAccount(
            user_id=user_id,
            name=name or "默认模拟账户",
            initial_cash=float(initial_cash),
            cash_available=float(initial_cash),
            total_assets=float(initial_cash),
            status="active",
        )
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account

    def get_account(self, account_id: int) -> PaperAccount:
        account = self.db.get(PaperAccount, account_id)
        if account is None:
            raise LookupError("模拟账户不存在")
        return account

    def get_or_create_default(self, user_id: int | None = None) -> PaperAccount:
        statement = select(PaperAccount)
        if user_id is None:
            statement = statement.where(PaperAccount.user_id.is_(None))
        else:
            statement = statement.where(PaperAccount.user_id == user_id)
        account = self.db.execute(statement.order_by(PaperAccount.id.asc())).scalar_one_or_none()
        if account is not None:
            return account
        return self.create_account("默认模拟账户", Decimal("100000"), user_id=user_id)

    def update_market_value(self, account_id: int) -> PaperAccount:
        account = self.get_account(account_id)
        positions = (
            self.db.execute(select(PaperPosition).where(PaperPosition.account_id == account_id, PaperPosition.quantity > 0))
            .scalars()
            .all()
        )
        market_value = sum(Decimal(str(position.market_value or 0)) for position in positions)
        unrealized = sum(Decimal(str(position.unrealized_pnl or 0)) for position in positions)
        account.market_value = float(market_value)
        account.unrealized_pnl = float(unrealized)
        account.total_assets = float(Decimal(str(account.cash_available or 0)) + market_value)
        self.db.flush()
        return account

    def reset_account(self, account_id: int) -> PaperAccount:
        account = self.get_account(account_id)
        for model in (PaperTrade, PaperPositionLot, PaperOrder, PaperPosition, PaperPerformanceSnapshot, PaperAgentRun):
            self.db.execute(delete(model).where(model.account_id == account_id))
        account.cash_available = account.initial_cash
        account.frozen_cash = 0
        account.market_value = 0
        account.total_assets = account.initial_cash
        account.realized_pnl = 0
        account.unrealized_pnl = 0
        account.max_drawdown_pct = 0
        account.status = "active"
        self.db.commit()
        self.db.refresh(account)
        return account

    def pause(self, account_id: int) -> PaperAccount:
        account = self.get_account(account_id)
        account.status = "paused"
        self.db.commit()
        self.db.refresh(account)
        return account

    def resume(self, account_id: int) -> PaperAccount:
        account = self.get_account(account_id)
        account.status = "active"
        self.db.commit()
        self.db.refresh(account)
        return account

    def check_balance(self, account_id: int, required: Decimal) -> bool:
        account = self.get_account(account_id)
        return Decimal(str(account.cash_available or 0)) >= required
