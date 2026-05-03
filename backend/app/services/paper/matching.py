from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.services.paper.fees import FeeDetail, calculate_fee
from app.services.paper.symbols import is_etf


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class MatchResult(str, Enum):
    FILLED = "filled"
    REJECTED = "rejected"
    PARTIAL = "partial"


@dataclass(frozen=True)
class MatchResponse:
    result: MatchResult
    filled_quantity: int
    avg_fill_price: Decimal | None
    reject_reason: str | None
    fee_detail: FeeDetail | None
    executed_at: datetime


class PaperMatchingEngine:
    def __init__(
        self,
        *,
        slippage_bps: int = 5,
        etf_slippage_bps: int = 2,
        quote_timeout_seconds: int = 120,
    ) -> None:
        self.slippage_bps = slippage_bps
        self.etf_slippage_bps = etf_slippage_bps
        self.quote_timeout_seconds = quote_timeout_seconds

    def match(
        self,
        *,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: int,
        limit_price: Decimal | None,
        current_price: Decimal,
        quote_time: datetime,
        is_suspended: bool,
        up_limit: Decimal | None = None,
        down_limit: Decimal | None = None,
    ) -> MatchResponse:
        now = datetime.now()
        price_error = self._price_reject_reason(current_price=current_price, limit_price=limit_price)
        if price_error:
            return self._rejected(price_error, now)
        reject_reason = self._reject_reason(
            side=side,
            quantity=quantity,
            quote_time=quote_time,
            now=now,
            is_suspended=is_suspended,
            current_price=current_price,
            up_limit=up_limit,
            down_limit=down_limit,
        )
        if reject_reason:
            return self._rejected(reject_reason, now)

        fill_price = self._fill_price(symbol, side, order_type, current_price, limit_price)
        if fill_price is None:
            return self._rejected("限价条件未满足，暂不成交。", now)
        fee = calculate_fee(symbol=symbol, side=side.value, price=fill_price, quantity=quantity)
        return MatchResponse(
            result=MatchResult.FILLED,
            filled_quantity=quantity,
            avg_fill_price=fill_price,
            reject_reason=None,
            fee_detail=fee,
            executed_at=now,
        )

    def _reject_reason(
        self,
        *,
        side: OrderSide,
        quantity: int,
        quote_time: datetime,
        now: datetime,
        is_suspended: bool,
        current_price: Decimal,
        up_limit: Decimal | None,
        down_limit: Decimal | None,
    ) -> str:
        if quantity <= 0 or quantity % 100 != 0:
            return "委托数量必须是 100 股整数倍。"
        if is_suspended:
            return "标的停牌，模拟委托被拒绝。"
        if (now - quote_time).total_seconds() > self.quote_timeout_seconds:
            return "行情时间过旧，模拟委托被拒绝。"
        if side == OrderSide.BUY and up_limit is not None and current_price >= up_limit:
            return "当前价格处于涨停附近，模拟买入被拒绝。"
        if side == OrderSide.SELL and down_limit is not None and current_price <= down_limit:
            return "当前价格处于跌停附近，模拟卖出被拒绝。"
        return ""

    def _fill_price(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        current_price: Decimal,
        limit_price: Decimal | None,
    ) -> Decimal | None:
        if order_type == OrderType.LIMIT:
            if limit_price is None:
                return None
            if side == OrderSide.BUY and current_price > limit_price:
                return None
            if side == OrderSide.SELL and current_price < limit_price:
                return None
            return limit_price
        bps = self.etf_slippage_bps if is_etf(symbol) else self.slippage_bps
        ratio = Decimal(bps) / Decimal(10000)
        multiplier = Decimal("1.0") + ratio if side == OrderSide.BUY else Decimal("1.0") - ratio
        return (current_price * multiplier).quantize(Decimal("0.0001"))

    @staticmethod
    def _rejected(reason: str, now: datetime) -> MatchResponse:
        return MatchResponse(
            result=MatchResult.REJECTED,
            filled_quantity=0,
            avg_fill_price=None,
            reject_reason=reason,
            fee_detail=None,
            executed_at=now,
        )

    @staticmethod
    def _price_reject_reason(*, current_price: Decimal, limit_price: Decimal | None) -> str:
        if current_price.is_nan() or current_price <= 0:
            return "行情价格无效，模拟委托被拒绝。"
        if limit_price is not None and (limit_price.is_nan() or limit_price <= 0):
            return "委托价格无效，模拟委托被拒绝。"
        return ""
