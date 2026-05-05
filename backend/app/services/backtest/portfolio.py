from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.services.paper.fees import FeeDetail
from app.services.paper.money import to_decimal, to_money
from app.services.paper.symbols import is_etf


@dataclass(frozen=True)
class PortfolioConfig:
    initial_cash: Decimal = Decimal("100000.00")
    max_position_pct: float = 0.2
    max_positions: int = 8
    lot_size: int = 100


@dataclass
class PositionLot:
    quantity: int
    remaining: int
    cost_price: Decimal
    entry_fee: Decimal
    available_date: str
    entry_date: str
    strategy_key: str = ""


@dataclass
class BacktestPosition:
    symbol: str
    name: str = ""
    quantity: int = 0
    cost_basis: Decimal = Decimal("0")
    entry_date: str = ""
    strategy_key: str = ""
    stop_loss: float | None = None
    take_profit: float | None = None
    max_holding_days: int = 5
    lots: list[PositionLot] = field(default_factory=list)

    def available_quantity(self, trade_date: str) -> int:
        return sum(lot.remaining for lot in self.lots if lot.available_date <= trade_date)


@dataclass(frozen=True)
class RealizedTrade:
    symbol: str
    name: str
    strategy_key: str
    entry_date: str
    exit_date: str
    quantity: int
    entry_price: float
    exit_price: float
    gross_pnl: float
    net_pnl: float
    return_pct: float
    fee_amount: float
    holding_days: int
    exit_reason: str


@dataclass(frozen=True)
class PortfolioSnapshot:
    trade_date: str
    cash: float
    market_value: float
    total_equity: float
    position_count: int


class BacktestPortfolio:
    def __init__(self, config: PortfolioConfig) -> None:
        self.config = config
        self.cash = to_money(config.initial_cash)
        self.positions: dict[str, BacktestPosition] = {}
        self.realized_trades: list[RealizedTrade] = []

    def total_equity(self, prices: dict[str, float] | None = None) -> Decimal:
        return to_money(self.cash + self.market_value(prices or {}))

    def market_value(self, prices: dict[str, float]) -> Decimal:
        total = Decimal("0")
        for symbol, position in self.positions.items():
            price = to_decimal(prices.get(symbol), position.cost_basis)
            total += price * Decimal(position.quantity)
        return to_money(total)

    def open_position_count(self) -> int:
        return sum(1 for position in self.positions.values() if position.quantity > 0)

    def can_open(self, symbol: str) -> bool:
        if self.positions.get(symbol, BacktestPosition(symbol=symbol)).quantity > 0:
            return False
        return self.open_position_count() < self.config.max_positions

    def target_quantity(self, *, price: Decimal, equity: Decimal, position_pct: float | None = None) -> int:
        if price <= 0:
            return 0
        pct = min(max(position_pct or self.config.max_position_pct, 0.0), self.config.max_position_pct)
        budget = min(self.cash, to_money(equity * Decimal(str(pct))))
        quantity = int(budget / price)
        quantity -= quantity % max(self.config.lot_size, 1)
        return max(quantity, 0)

    def buy(
        self,
        *,
        symbol: str,
        name: str,
        quantity: int,
        price: Decimal,
        fee: FeeDetail,
        trade_date: str,
        next_trade_date: str | None,
        strategy_key: str,
        stop_loss: float | None,
        take_profit: float | None,
        max_holding_days: int,
    ) -> None:
        if quantity <= 0:
            return
        self.cash = to_money(self.cash - fee.net_amount)
        position = self.positions.get(symbol)
        if position is None:
            position = BacktestPosition(symbol=symbol, name=name or symbol)
            self.positions[symbol] = position
        old_quantity = position.quantity
        new_quantity = old_quantity + quantity
        position.cost_basis = _weighted_cost(position.cost_basis, old_quantity, price, quantity)
        position.quantity = new_quantity
        position.name = name or position.name or symbol
        position.entry_date = position.entry_date or trade_date
        position.strategy_key = strategy_key or position.strategy_key
        position.stop_loss = stop_loss
        position.take_profit = take_profit
        position.max_holding_days = max(max_holding_days, 1)
        position.lots.append(
            PositionLot(
                quantity=quantity,
                remaining=quantity,
                cost_price=price,
                entry_fee=fee.total_fee,
                available_date=trade_date if is_etf(symbol) else (next_trade_date or trade_date),
                entry_date=trade_date,
                strategy_key=strategy_key,
            )
        )

    def sell(
        self,
        *,
        symbol: str,
        quantity: int,
        price: Decimal,
        fee: FeeDetail,
        trade_date: str,
        exit_reason: str,
    ) -> list[RealizedTrade]:
        position = self.positions.get(symbol)
        if position is None or quantity <= 0:
            return []
        sell_quantity = min(quantity, position.available_quantity(trade_date), position.quantity)
        if sell_quantity <= 0:
            return []
        consumed = self._consume_lots(position, sell_quantity, trade_date)
        if not consumed:
            return []
        self.cash = to_money(self.cash + fee.net_amount)
        position.quantity -= sell_quantity
        if position.quantity <= 0:
            self.positions.pop(symbol, None)
        trades = [
            _realized_trade(
                position=position,
                lot=lot,
                quantity=used,
                exit_price=price,
                exit_fee=fee.total_fee * Decimal(used) / Decimal(max(sell_quantity, 1)),
                trade_date=trade_date,
                exit_reason=exit_reason,
            )
            for lot, used in consumed
        ]
        self.realized_trades.extend(trades)
        return trades

    def snapshot(self, trade_date: str, prices: dict[str, float]) -> PortfolioSnapshot:
        market_value = self.market_value(prices)
        total_equity = to_money(self.cash + market_value)
        return PortfolioSnapshot(
            trade_date=trade_date,
            cash=float(self.cash),
            market_value=float(market_value),
            total_equity=float(total_equity),
            position_count=self.open_position_count(),
        )

    def _consume_lots(
        self,
        position: BacktestPosition,
        quantity: int,
        trade_date: str,
    ) -> list[tuple[PositionLot, int]]:
        remaining = quantity
        consumed: list[tuple[PositionLot, int]] = []
        for lot in sorted(position.lots, key=lambda item: (item.available_date, item.entry_date)):
            if remaining <= 0:
                break
            if lot.remaining <= 0 or lot.available_date > trade_date:
                continue
            used = min(remaining, lot.remaining)
            lot.remaining -= used
            remaining -= used
            consumed.append((lot, used))
        return consumed if remaining == 0 else []


def _weighted_cost(current_cost: Decimal, current_qty: int, new_cost: Decimal, new_qty: int) -> Decimal:
    if current_qty <= 0:
        return new_cost
    return (current_cost * current_qty + new_cost * new_qty) / Decimal(current_qty + new_qty)


def _realized_trade(
    *,
    position: BacktestPosition,
    lot: PositionLot,
    quantity: int,
    exit_price: Decimal,
    exit_fee: Decimal,
    trade_date: str,
    exit_reason: str,
) -> RealizedTrade:
    gross_pnl = (exit_price - lot.cost_price) * Decimal(quantity)
    entry_fee = lot.entry_fee * Decimal(quantity) / Decimal(max(lot.quantity, 1))
    total_fee = entry_fee + exit_fee
    net_pnl = gross_pnl - total_fee
    cost_amount = lot.cost_price * Decimal(max(quantity, 1))
    return RealizedTrade(
        symbol=position.symbol,
        name=position.name,
        strategy_key=lot.strategy_key or position.strategy_key,
        entry_date=lot.entry_date,
        exit_date=trade_date,
        quantity=quantity,
        entry_price=float(lot.cost_price),
        exit_price=float(exit_price),
        gross_pnl=float(to_money(gross_pnl)),
        net_pnl=float(to_money(net_pnl)),
        return_pct=float((net_pnl / max(cost_amount, Decimal("0.01"))) * Decimal("100")),
        fee_amount=float(to_money(total_fee)),
        holding_days=_calendar_days(lot.entry_date, trade_date),
        exit_reason=exit_reason,
    )


def _calendar_days(entry_date: str, exit_date: str) -> int:
    try:
        start = datetime.strptime(entry_date, "%Y-%m-%d").date()
        end = datetime.strptime(exit_date, "%Y-%m-%d").date()
    except ValueError:
        return 0
    return max((end - start).days, 0)
