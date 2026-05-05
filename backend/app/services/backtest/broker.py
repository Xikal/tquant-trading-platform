from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.services.backtest.data_provider import BacktestSignal, DailyBar
from app.services.paper.fees import FeeDetail
from app.services.paper.matching import MatchResult, OrderSide, OrderType, PaperMatchingEngine
from app.services.paper.money import to_decimal


class ExecutionModel(str, Enum):
    OPEN_PRICE = "open_price"
    VWAP = "vwap"
    CLOSE_PRICE = "close_price"
    ENTRY_ZONE_TOUCH = "entry_zone_touch"
    CONSERVATIVE_SLIPPAGE = "conservative_slippage"


@dataclass(frozen=True)
class ExecutionRequest:
    trade_date: str
    symbol: str
    side: str
    quantity: int
    bar: DailyBar
    execution_model: str
    signal: BacktestSignal | None = None
    requested_price: float | None = None
    reason: str = ""


@dataclass(frozen=True)
class ExecutionResult:
    trade_date: str
    symbol: str
    side: str
    quantity: int
    status: str
    fill_price: Decimal | None = None
    fee_detail: FeeDetail | None = None
    reject_reason: str = ""
    execution_model: str = ""
    strategy_key: str = ""
    reason: str = ""


class BacktestBroker:
    """Daily execution adapter using paper matching and fee semantics."""

    def __init__(self, matching_engine: PaperMatchingEngine | None = None) -> None:
        self.matching = matching_engine or PaperMatchingEngine()

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        model = _execution_model(request.execution_model)
        selected_price = _selected_price(request, model)
        if selected_price is None or selected_price <= 0:
            return _rejected(request, "执行价格不可用。")
        if request.bar.is_suspended:
            return _rejected(request, "标的停牌或日线无效，回测委托被拒绝。")

        side = OrderSide.BUY if request.side == "buy" else OrderSide.SELL
        order_type = OrderType.MARKET if model == ExecutionModel.CONSERVATIVE_SLIPPAGE else OrderType.LIMIT
        limit_price = None if order_type == OrderType.MARKET else to_decimal(selected_price)
        match = self.matching.match(
            symbol=request.symbol,
            side=side,
            order_type=order_type,
            quantity=request.quantity,
            limit_price=limit_price,
            current_price=to_decimal(selected_price),
            quote_time=datetime.now(),
            is_suspended=request.bar.is_suspended,
            up_limit=to_decimal(selected_price) if _is_limit_up(request.bar) else None,
            down_limit=to_decimal(selected_price) if _is_limit_down(request.bar) else None,
        )
        if match.result != MatchResult.FILLED or match.avg_fill_price is None or match.fee_detail is None:
            return _rejected(request, match.reject_reason or "回测委托未成交。")
        return ExecutionResult(
            trade_date=request.trade_date,
            symbol=request.symbol,
            side=request.side,
            quantity=match.filled_quantity,
            status="filled",
            fill_price=match.avg_fill_price,
            fee_detail=match.fee_detail,
            execution_model=model.value,
            strategy_key=request.signal.strategy_key if request.signal else "",
            reason=request.reason,
        )


def _execution_model(value: str) -> ExecutionModel:
    try:
        return ExecutionModel(value)
    except ValueError:
        return ExecutionModel.CONSERVATIVE_SLIPPAGE


def _selected_price(request: ExecutionRequest, model: ExecutionModel) -> float | None:
    if request.requested_price is not None:
        return float(request.requested_price)
    bar = request.bar
    if model == ExecutionModel.OPEN_PRICE:
        return bar.open_price
    if model == ExecutionModel.VWAP:
        return bar.vwap
    if model == ExecutionModel.CLOSE_PRICE:
        return bar.close_price
    if model == ExecutionModel.ENTRY_ZONE_TOUCH and request.side == "buy":
        return _entry_zone_price(bar, request.signal)
    if model == ExecutionModel.CONSERVATIVE_SLIPPAGE:
        return max(bar.open_price, bar.close_price) if request.side == "buy" else min(bar.open_price, bar.close_price)
    return bar.close_price


def _entry_zone_price(bar: DailyBar, signal: BacktestSignal | None) -> float | None:
    if signal is None or signal.entry_zone_low is None or signal.entry_zone_high is None:
        return None
    low = min(signal.entry_zone_low, signal.entry_zone_high)
    high = max(signal.entry_zone_low, signal.entry_zone_high)
    if bar.low_price > high or bar.high_price < low:
        return None
    return high


def _is_limit_up(bar: DailyBar) -> bool:
    return float(bar.pct_chg or 0) >= 9.8


def _is_limit_down(bar: DailyBar) -> bool:
    return float(bar.pct_chg or 0) <= -9.8


def _rejected(request: ExecutionRequest, reason: str) -> ExecutionResult:
    return ExecutionResult(
        trade_date=request.trade_date,
        symbol=request.symbol,
        side=request.side,
        quantity=request.quantity,
        status="rejected",
        reject_reason=reason,
        execution_model=request.execution_model,
        strategy_key=request.signal.strategy_key if request.signal else "",
        reason=request.reason,
    )
