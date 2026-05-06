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
    RiskEvent,
)
from app.services.paper.money import ZERO, to_decimal


class PaperAccountService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_account(self, name: str, initial_cash: Decimal, user_id: int | None = None) -> PaperAccount:
        account = PaperAccount(
            user_id=user_id,
            name=name or "默认模拟账户",
            initial_cash=initial_cash,
            cash_available=initial_cash,
            total_assets=initial_cash,
            status="active",
        )
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account

    def get_account(self, account_id: int, *, for_update: bool = False) -> PaperAccount:
        if for_update:
            account = (
                self.db.execute(
                    select(PaperAccount)
                    .where(PaperAccount.id == account_id)
                    .with_for_update()
                )
                .scalars()
                .one_or_none()
            )
        else:
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
        active_statement = statement.where(PaperAccount.status == "active").order_by(PaperAccount.id.asc()).limit(1)
        account = self.db.execute(active_statement).scalars().first()
        if account is None:
            account = self.db.execute(statement.order_by(PaperAccount.id.asc()).limit(1)).scalars().first()
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
        market_value = sum(to_decimal(position.market_value) for position in positions)
        unrealized = sum(to_decimal(position.unrealized_pnl) for position in positions)
        account.market_value = market_value
        account.unrealized_pnl = unrealized
        account.total_assets = to_decimal(account.cash_available) + market_value
        self.db.flush()
        return account

    def reset_account(self, account_id: int) -> PaperAccount:
        account = self.get_account(account_id)
        for model in (PaperTrade, PaperPositionLot, PaperOrder, PaperPosition, PaperPerformanceSnapshot, PaperAgentRun):
            self.db.execute(delete(model).where(model.account_id == account_id))
        account.cash_available = account.initial_cash
        account.frozen_cash = ZERO
        account.market_value = ZERO
        account.total_assets = account.initial_cash
        account.realized_pnl = ZERO
        account.unrealized_pnl = ZERO
        account.max_drawdown_pct = ZERO
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

    def resume_if_safe_for_auto_trading(self, account_id: int) -> PaperAccount:
        account = self.get_account(account_id)
        if account.status != "paused" or self._has_blocking_risk_event(account_id):
            return account
        account.status = "active"
        self.db.commit()
        self.db.refresh(account)
        return account

    def check_balance(self, account_id: int, required: Decimal) -> bool:
        account = self.get_account(account_id)
        return to_decimal(account.cash_available) >= required

    def check_balance_locked(self, account_id: int, required: Decimal) -> bool:
        account = self.get_account(account_id, for_update=True)
        return to_decimal(account.cash_available) >= required

    def _has_blocking_risk_event(self, account_id: int) -> bool:
        return self.db.execute(
            select(RiskEvent.id)
            .where(
                RiskEvent.account_id == account_id,
                RiskEvent.status == "open",
                RiskEvent.severity.in_(["high", "critical"]),
            )
            .limit(1)
        ).scalar_one_or_none() is not None
