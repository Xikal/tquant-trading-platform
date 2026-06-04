from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal


ExecutionEventKind = Literal["signal", "order", "fill", "position", "exit"]


@dataclass(frozen=True)
class ExecutionEvent:
    kind: ExecutionEventKind
    symbol: str
    trade_date: str
    strategy_key: str = ""
    source: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def as_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionSignal(ExecutionEvent):
    kind: ExecutionEventKind = "signal"
    symbol: str = ""
    trade_date: str = ""
    strategy_key: str = ""
    source: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    signal_state: str = "watch"
    score: float | None = None


@dataclass(frozen=True)
class ExecutionOrder(ExecutionEvent):
    kind: ExecutionEventKind = "order"
    symbol: str = ""
    trade_date: str = ""
    strategy_key: str = ""
    source: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    side: Literal["buy", "sell"] = "buy"
    quantity: int = 0
    requested_price: Decimal | None = None
    order_type: str = "market"


@dataclass(frozen=True)
class ExecutionFill(ExecutionEvent):
    kind: ExecutionEventKind = "fill"
    symbol: str = ""
    trade_date: str = ""
    strategy_key: str = ""
    source: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    side: Literal["buy", "sell"] = "buy"
    quantity: int = 0
    fill_price: Decimal | None = None
    fee_amount: Decimal = Decimal("0")
    filled_at: datetime | None = None


@dataclass(frozen=True)
class ExecutionPosition(ExecutionEvent):
    kind: ExecutionEventKind = "position"
    symbol: str = ""
    trade_date: str = ""
    strategy_key: str = ""
    source: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    quantity: int = 0
    available_quantity: int = 0
    cost_basis: Decimal = Decimal("0")
    market_price: Decimal | None = None


@dataclass(frozen=True)
class ExitEvent(ExecutionEvent):
    kind: ExecutionEventKind = "exit"
    symbol: str = ""
    trade_date: str = ""
    strategy_key: str = ""
    source: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    quantity: int = 0
    exit_price: Decimal | None = None
    exit_reason: str = ""
    return_pct: float | None = None
