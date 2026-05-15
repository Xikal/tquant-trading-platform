from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable

from app.models.entities import PaperTrade
from app.services.paper.money import ZERO, to_decimal


@dataclass
class ReplayTradeIssue:
    trade_id: int
    order_id: int
    symbol: str
    side: str
    original_quantity: int
    valid_quantity: int
    invalid_quantity: int
    original_net_amount: Decimal
    valid_net_amount: Decimal
    original_fee_total: Decimal
    valid_fee_total: Decimal
    reason: str


@dataclass
class ReplaySymbolLedger:
    symbol: str
    name: str = ""
    buy_quantity: int = 0
    sell_quantity: int = 0
    current_quantity: int = 0
    avg_cost: Decimal | None = None
    realized_pnl: Decimal = ZERO
    unrealized_pnl: Decimal = ZERO
    total_fees: Decimal = ZERO
    replay_complete: bool = True


@dataclass
class ReplayResult:
    ledgers: dict[str, ReplaySymbolLedger] = field(default_factory=dict)
    issues: list[ReplayTradeIssue] = field(default_factory=list)
    corrected_cash_delta: Decimal = ZERO
    corrected_realized_pnl: Decimal = ZERO


@dataclass
class _Lot:
    quantity: int
    total_cost: Decimal


def replay_trades(rows: Iterable[tuple[PaperTrade, str]]) -> ReplayResult:
    result = ReplayResult()
    lots_by_symbol: dict[str, list[_Lot]] = {}
    for trade, order_name in rows:
        symbol = trade.symbol
        ledger = result.ledgers.setdefault(symbol, ReplaySymbolLedger(symbol=symbol, name=order_name or symbol))
        if order_name and ledger.name == symbol:
            ledger.name = order_name
        qty = int(trade.quantity or 0)
        if qty <= 0:
            continue
        fee_total = trade_fee_total(trade)
        net_amount = to_decimal(trade.net_amount)
        lots = lots_by_symbol.setdefault(symbol, [])
        if trade.side == "buy":
            ledger.buy_quantity += qty
            ledger.total_fees += fee_total
            lots.append(_Lot(quantity=qty, total_cost=net_amount))
            result.corrected_cash_delta -= net_amount
            continue
        valid_qty = min(qty, sum(lot.quantity for lot in lots))
        valid_ratio = Decimal(valid_qty) / Decimal(qty) if qty > 0 else ZERO
        valid_net_amount = (net_amount * valid_ratio).quantize(Decimal("0.01"))
        valid_fee_total = (fee_total * valid_ratio).quantize(Decimal("0.0001"))
        if valid_qty < qty:
            ledger.replay_complete = False
            result.issues.append(
                ReplayTradeIssue(
                    trade_id=int(trade.id),
                    order_id=int(trade.order_id),
                    symbol=symbol,
                    side=trade.side,
                    original_quantity=qty,
                    valid_quantity=valid_qty,
                    invalid_quantity=qty - valid_qty,
                    original_net_amount=net_amount,
                    valid_net_amount=valid_net_amount,
                    original_fee_total=fee_total,
                    valid_fee_total=valid_fee_total,
                    reason="卖出数量超过历史可用持仓，已识别为异常成交。",
                )
            )
        if valid_qty <= 0:
            continue
        realized_cost = _consume_cost(lots, valid_qty)
        ledger.sell_quantity += valid_qty
        ledger.total_fees += valid_fee_total
        ledger.realized_pnl += valid_net_amount - realized_cost
        result.corrected_cash_delta += valid_net_amount
        result.corrected_realized_pnl += valid_net_amount - realized_cost
    for symbol, ledger in result.ledgers.items():
        remaining_lots = lots_by_symbol.get(symbol, [])
        remaining_qty = sum(lot.quantity for lot in remaining_lots)
        ledger.current_quantity = remaining_qty
        if remaining_qty > 0:
            total_cost = sum(lot.total_cost for lot in remaining_lots)
            ledger.avg_cost = _safe_div(total_cost, remaining_qty)
    return result


def trade_fee_total(trade: PaperTrade) -> Decimal:
    return to_decimal(trade.commission) + to_decimal(trade.stamp_tax) + to_decimal(trade.transfer_fee)


def _consume_cost(lots: list[_Lot], quantity: int) -> Decimal:
    remaining = quantity
    total_cost = ZERO
    while remaining > 0 and lots:
        lot = lots[0]
        matched = min(remaining, lot.quantity)
        if matched == lot.quantity:
            consumed_cost = lot.total_cost
        else:
            consumed_cost = lot.total_cost * Decimal(matched) / Decimal(lot.quantity)
        total_cost += consumed_cost
        lot.total_cost -= consumed_cost
        lot.quantity -= matched
        remaining -= matched
        if lot.quantity <= 0:
            lots.pop(0)
    return total_cost.quantize(Decimal("0.01"))


def _safe_div(value: Decimal, quantity: int) -> Decimal:
    if quantity <= 0:
        return ZERO
    return (value / Decimal(quantity)).quantize(Decimal("0.0001"))
