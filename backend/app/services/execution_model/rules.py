from __future__ import annotations

from decimal import Decimal

from app.services.paper.money import to_decimal
from app.services.paper.symbols import can_sell_same_day


def weighted_cost_basis(current_cost: Decimal, current_qty: int, new_cost: Decimal, new_qty: int) -> Decimal:
    if current_qty <= 0:
        return to_decimal(new_cost)
    if new_qty <= 0:
        return to_decimal(current_cost)
    return to_decimal(
        (to_decimal(current_cost) * Decimal(current_qty) + to_decimal(new_cost) * Decimal(new_qty))
        / Decimal(current_qty + new_qty)
    )


def available_quantity_for_date(
    lots: list[tuple[int, str]],
    *,
    trade_date: str,
    symbol: str = "",
) -> int:
    if can_sell_same_day(symbol):
        return sum(max(int(quantity or 0), 0) for quantity, _available_date in lots)
    return sum(
        max(int(quantity or 0), 0)
        for quantity, available_date in lots
        if str(available_date or "") <= str(trade_date or "")
    )


def lot_sized_quantity(raw_quantity: int, *, lot_size: int = 100) -> int:
    size = max(int(lot_size or 1), 1)
    quantity = max(int(raw_quantity or 0), 0)
    return quantity - quantity % size


def position_return_pct(*, entry_price: Decimal, exit_price: Decimal) -> float:
    entry = to_decimal(entry_price)
    if entry <= 0:
        return 0.0
    return float((to_decimal(exit_price) - entry) / entry * Decimal("100"))
