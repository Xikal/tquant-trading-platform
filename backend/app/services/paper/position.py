from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import PaperPosition, PaperPositionLot


class PaperPositionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_positions(self, account_id: int) -> list[PaperPosition]:
        self.refresh_available_quantities(account_id)
        return (
            self.db.execute(
                select(PaperPosition)
                .where(PaperPosition.account_id == account_id, PaperPosition.quantity > 0)
                .order_by(PaperPosition.updated_at.desc())
            )
            .scalars()
            .all()
        )

    def get_position(self, account_id: int, symbol: str) -> PaperPosition | None:
        self.refresh_available_quantities(account_id, symbol=symbol)
        return self.db.execute(
            select(PaperPosition).where(PaperPosition.account_id == account_id, PaperPosition.symbol == symbol)
        ).scalar_one_or_none()

    def add_position(
        self,
        *,
        account_id: int,
        symbol: str,
        name: str,
        quantity: int,
        cost_price: Decimal,
        strategy_key: str = "",
        source_order_id: int | None = None,
        trade_date: date | None = None,
    ) -> PaperPosition:
        row = self.get_position(account_id, symbol)
        if row is None:
            row = PaperPosition(
                account_id=account_id,
                symbol=symbol,
                name=name or symbol,
                quantity=0,
                available_quantity=0,
                cost_basis=float(cost_price),
            )
            self.db.add(row)
            self.db.flush()
        old_qty = int(row.quantity or 0)
        new_qty = old_qty + quantity
        row.cost_basis = float(_weighted_cost(Decimal(str(row.cost_basis or 0)), old_qty, cost_price, quantity))
        row.quantity = new_qty
        row.name = name or row.name or symbol
        row.strategy_sources = _merge_strategy_source(row.strategy_sources, strategy_key)
        self.db.add(
            PaperPositionLot(
                account_id=account_id,
                position_id=row.id,
                symbol=symbol,
                quantity=quantity,
                remaining=quantity,
                available_date=_next_business_day(trade_date or date.today()),
                cost_price=float(cost_price),
                source_order_id=source_order_id,
            )
        )
        self.refresh_available_quantities(account_id, symbol=symbol)
        return row

    def reduce_position(self, *, account_id: int, symbol: str, quantity: int) -> PaperPosition:
        row = self.get_position(account_id, symbol)
        if row is None or row.available_quantity < quantity:
            raise ValueError("可卖数量不足，模拟卖出被拒绝。")
        remaining_to_sell = quantity
        lots = (
            self.db.execute(
                select(PaperPositionLot)
                .where(
                    PaperPositionLot.account_id == account_id,
                    PaperPositionLot.symbol == symbol,
                    PaperPositionLot.remaining > 0,
                    PaperPositionLot.available_date <= date.today(),
                )
                .order_by(PaperPositionLot.available_date.asc(), PaperPositionLot.id.asc())
            )
            .scalars()
            .all()
        )
        for lot in lots:
            if remaining_to_sell <= 0:
                break
            used = min(remaining_to_sell, lot.remaining)
            lot.remaining -= used
            remaining_to_sell -= used
        if remaining_to_sell > 0:
            raise ValueError("T+1 批次数量不足，模拟卖出被拒绝。")
        row.quantity = max(0, row.quantity - quantity)
        self.refresh_available_quantities(account_id, symbol=symbol)
        return row

    def refresh_available_quantities(self, account_id: int, symbol: str | None = None) -> None:
        positions = (
            self.db.execute(
                select(PaperPosition).where(
                    PaperPosition.account_id == account_id,
                    *((PaperPosition.symbol == symbol,) if symbol else ()),
                )
            )
            .scalars()
            .all()
        )
        for position in positions:
            available = self.db.execute(
                select(PaperPositionLot).where(
                    PaperPositionLot.account_id == account_id,
                    PaperPositionLot.symbol == position.symbol,
                    PaperPositionLot.remaining > 0,
                    PaperPositionLot.available_date <= date.today(),
                )
            ).scalars().all()
            position.available_quantity = sum(lot.remaining for lot in available)

    def refresh_quotes(self, account_id: int, prices: dict[str, Decimal]) -> None:
        for symbol, price in prices.items():
            row = self.get_position(account_id, symbol)
            if row is None:
                continue
            row.latest_price = float(price)
            row.market_value = float(price * Decimal(row.quantity))
            row.unrealized_pnl = float((price - Decimal(str(row.cost_basis or 0))) * Decimal(row.quantity))
            cost_amount = Decimal(str(row.cost_basis or 0)) * Decimal(max(row.quantity, 1))
            row.unrealized_pnl_pct = float(Decimal(str(row.unrealized_pnl or 0)) / max(cost_amount, Decimal("0.01")) * 100)


def _weighted_cost(current_cost: Decimal, current_qty: int, new_cost: Decimal, new_qty: int) -> Decimal:
    if current_qty <= 0:
        return new_cost
    return ((current_cost * current_qty) + (new_cost * new_qty)) / (current_qty + new_qty)


def _next_business_day(value: date) -> date:
    next_day = value + timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    return next_day


def _merge_strategy_source(raw: str, strategy_key: str) -> str:
    try:
        values = list(json.loads(raw or "[]"))
    except Exception:
        values = []
    if strategy_key and strategy_key not in values:
        values.append(strategy_key)
    return json.dumps(values, ensure_ascii=False)

