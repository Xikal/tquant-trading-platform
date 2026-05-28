from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import PaperPosition, PaperPositionLot
from app.core.timezone import beijing_today
from app.services.market.trading_calendar import last_a_share_trading_day, next_a_share_trading_day
from app.services.paper.money import CENT, to_decimal
from app.services.paper.symbols import can_sell_same_day


class PaperPositionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_positions(self, account_id: int) -> list[PaperPosition]:
        self.refresh_available_quantities(account_id)
        return (
            self.db.execute(
                select(PaperPosition)
                .options(selectinload(PaperPosition.lots))
                .where(PaperPosition.account_id == account_id, PaperPosition.quantity > 0)
                .order_by(PaperPosition.updated_at.desc())
            )
            .scalars()
            .all()
        )

    def get_position(self, account_id: int, symbol: str) -> PaperPosition | None:
        self.refresh_available_quantities(account_id, symbol=symbol)
        return self.db.execute(
            select(PaperPosition)
            .options(selectinload(PaperPosition.lots))
            .where(PaperPosition.account_id == account_id, PaperPosition.symbol == symbol)
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
                cost_basis=cost_price,
            )
            self.db.add(row)
            self.db.flush()
        old_qty = int(row.quantity or 0)
        new_qty = old_qty + quantity
        row.cost_basis = _weighted_cost(to_decimal(row.cost_basis), old_qty, cost_price, quantity)
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
                available_date=_available_date_for_buy(symbol, trade_date or beijing_today()),
                cost_price=cost_price,
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
        available_as_of = _available_as_of_for_sell(symbol)
        lots = (
            self.db.execute(
                select(PaperPositionLot)
                .where(
                    PaperPositionLot.account_id == account_id,
                    PaperPositionLot.symbol == symbol,
                    PaperPositionLot.remaining > 0,
                    PaperPositionLot.available_date <= available_as_of,
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
        if not positions:
            return
        symbols = [position.symbol for position in positions]
        lot_statement = (
            select(PaperPositionLot.symbol, PaperPositionLot.remaining, PaperPositionLot.available_date)
            .where(
                PaperPositionLot.account_id == account_id,
                PaperPositionLot.remaining > 0,
                PaperPositionLot.symbol.in_(symbols),
            )
        )
        available_by_symbol: dict[str, int] = {}
        for symbol_value, remaining, available_date in self.db.execute(lot_statement).all():
            if available_date <= _available_as_of_for_sell(str(symbol_value)):
                available_by_symbol[str(symbol_value)] = available_by_symbol.get(str(symbol_value), 0) + int(remaining or 0)
        for position in positions:
            position.available_quantity = available_by_symbol.get(position.symbol, 0)

    def refresh_quotes(self, account_id: int, prices: dict[str, Decimal]) -> None:
        if not prices:
            return
        positions = (
            self.db.execute(
                select(PaperPosition).where(
                    PaperPosition.account_id == account_id,
                    PaperPosition.symbol.in_(list(prices.keys())),
                )
            )
            .scalars()
            .all()
        )
        self.refresh_available_quantities(account_id)
        for row in positions:
            price = prices.get(row.symbol)
            if price is None:
                continue
            row.latest_price = price
            row.market_value = price * Decimal(row.quantity)
            row.unrealized_pnl = (price - to_decimal(row.cost_basis)) * Decimal(row.quantity)
            cost_amount = to_decimal(row.cost_basis) * Decimal(max(row.quantity, 1))
            row.unrealized_pnl_pct = to_decimal(row.unrealized_pnl) / max(cost_amount, CENT) * 100


def _weighted_cost(current_cost: Decimal, current_qty: int, new_cost: Decimal, new_qty: int) -> Decimal:
    if current_qty <= 0:
        return new_cost
    return ((current_cost * current_qty) + (new_cost * new_qty)) / (current_qty + new_qty)


def _next_business_day(value: date) -> date:
    return next_a_share_trading_day(value)


def _available_date_for_buy(symbol: str, trade_date: date) -> date:
    # A 股普通股票 T+1；只有 ETF universe 放行的标的才按 T+0 可回转处理。
    return trade_date if can_sell_same_day(symbol) else _next_business_day(trade_date)


def _available_as_of_for_sell(symbol: str) -> date:
    return beijing_today() if can_sell_same_day(symbol) else last_a_share_trading_day(beijing_today())


def _merge_strategy_source(raw: str, strategy_key: str) -> str:
    try:
        values = list(json.loads(raw or "[]"))
    except Exception:
        values = []
    if strategy_key and strategy_key not in values:
        values.append(strategy_key)
    return json.dumps(values, ensure_ascii=False)
