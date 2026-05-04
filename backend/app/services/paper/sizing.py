from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.services.paper.admission import AdmissionResult


@dataclass(frozen=True)
class SizedOrder:
    symbol: str
    name: str
    side: str
    order_type: str
    quantity: int
    price: Decimal
    current_price: Decimal
    strategy_key: str
    reason: str
    signal_snapshot: dict[str, Any]
    source: str = "auto"

    def to_plan_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": self.quantity,
            "price": str(self.price),
            "current_price": str(self.current_price),
            "quote_time": datetime.now(),
            "is_suspended": bool(self.signal_snapshot.get("is_suspended") or False),
            "source": self.source,
            "strategy_key": self.strategy_key,
            "reason": self.reason,
            "signal_snapshot": self.signal_snapshot,
            "require_intraday_confirmation": bool(self.signal_snapshot.get("require_intraday_confirmation") or False),
        }


class PositionSizer:
    """Convert admitted priority-board candidates into paper buy plans."""

    def __init__(self, *, max_position_pct: float = 0.10, max_cash_pct: float = 0.30) -> None:
        self.max_position_pct = Decimal(str(max_position_pct))
        self.max_cash_pct = Decimal(str(max_cash_pct))

    def calculate(
        self,
        *,
        candidates: list[AdmissionResult],
        total_assets: float,
        available_cash: float,
        max_orders: int = 5,
    ) -> list[SizedOrder]:
        if total_assets <= 0 or available_cash <= 0 or max_orders <= 0:
            return []

        remaining_cash = Decimal(str(available_cash))
        total_assets_value = Decimal(str(total_assets))
        orders: list[SizedOrder] = []
        for candidate in sorted(candidates, key=lambda item: item.priority_score, reverse=True):
            if len(orders) >= max_orders:
                break
            order = self._size_candidate(candidate, total_assets=total_assets_value, remaining_cash=remaining_cash)
            if order is None:
                continue
            orders.append(order)
            remaining_cash -= Decimal(order.quantity) * order.current_price
            if remaining_cash <= 0:
                break
        return orders

    def _size_candidate(self, candidate: AdmissionResult, *, total_assets: Decimal, remaining_cash: Decimal) -> SizedOrder | None:
        current_price = _current_price(candidate.signal)
        if current_price <= 0:
            return None

        price_value = current_price
        max_value = min(total_assets * self.max_position_pct, remaining_cash * self.max_cash_pct)
        quantity = _round_lot_decimal(max_value / price_value)
        if quantity < 100:
            return None
        if Decimal(quantity) * price_value > remaining_cash:
            quantity = _round_lot_decimal(remaining_cash / price_value)
        if quantity < 100:
            return None

        strategy_key = _strategy_key(candidate.signal)
        return SizedOrder(
            symbol=candidate.symbol,
            name=candidate.name,
            side="buy",
            order_type="market",
            quantity=quantity,
            price=current_price,
            current_price=current_price,
            strategy_key=strategy_key,
            reason=_reason(candidate, strategy_key=strategy_key),
            signal_snapshot=dict(candidate.signal),
        )


def _current_price(signal: dict[str, Any]) -> Decimal:
    for key in ("latest_price", "current_price", "last_price", "price"):
        try:
            value = Decimal(str(signal.get(key) or "0"))
        except Exception:
            value = Decimal("0")
        if value > 0:
            return value
    return Decimal("0")


def _round_lot_decimal(raw_quantity: Decimal) -> int:
    return int(raw_quantity // Decimal(100) * 100)


def _strategy_key(signal: dict[str, Any]) -> str:
    value = signal.get("strategy_key")
    if value:
        return str(value)
    strategy_keys = signal.get("strategy_keys") or []
    if isinstance(strategy_keys, list) and strategy_keys:
        return str(strategy_keys[0])
    return ""


def _reason(candidate: AdmissionResult, *, strategy_key: str) -> str:
    title = candidate.signal.get("strategy_title") or strategy_key or "优先级榜信号"
    return f"自动调入: {title}，调度分{candidate.priority_score:.0f}"
