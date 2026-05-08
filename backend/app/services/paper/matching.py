from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.services.paper.fees import FeeDetail, calculate_fee
from app.services.paper.symbols import is_etf, price_tick
from app.core.timezone import beijing_now
from app.services.quant.runtime_parameters import get_backtest_execution


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
        slippage_bps: int | None = None,
        etf_slippage_bps: int | None = None,
        quote_timeout_seconds: int = 120,
    ) -> None:
        params = _execution_params()
        self.slippage_bps = int(slippage_bps if slippage_bps is not None else _float_param(params, "paper_slippage_stock_bps", 5.0))
        self.etf_slippage_bps = int(etf_slippage_bps if etf_slippage_bps is not None else _float_param(params, "paper_slippage_etf_bps", 2.0))
        self.mid_liquidity_slippage_bps = int(_float_param(params, "paper_slippage_mid_liquidity_bps", 8.0))
        self.low_liquidity_slippage_bps = int(_float_param(params, "paper_slippage_low_liquidity_bps", 15.0))
        self.mid_liquidity_amount = Decimal(str(_float_param(params, "paper_slippage_mid_liquidity_amount", 100_000_000.0)))
        self.low_liquidity_amount = Decimal(str(_float_param(params, "paper_slippage_low_liquidity_amount", 30_000_000.0)))
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
        traded_amount: Decimal | None = None,
    ) -> MatchResponse:
        now = beijing_now().replace(tzinfo=None)
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

        fill_price = self._fill_price(symbol, side, order_type, current_price, limit_price, traded_amount=traded_amount)
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
        *,
        traded_amount: Decimal | None = None,
    ) -> Decimal | None:
        if order_type == OrderType.LIMIT:
            if limit_price is None:
                return None
            if side == OrderSide.BUY and current_price > limit_price:
                return None
            if side == OrderSide.SELL and current_price < limit_price:
                return None
            return limit_price.quantize(Decimal(price_tick(symbol)))
        bps = self._slippage_bps(symbol, traded_amount=traded_amount)
        ratio = Decimal(bps) / Decimal(10000)
        multiplier = Decimal("1.0") + ratio if side == OrderSide.BUY else Decimal("1.0") - ratio
        return (current_price * multiplier).quantize(Decimal(price_tick(symbol)))

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

    def _slippage_bps(self, symbol: str, *, traded_amount: Decimal | None) -> int:
        if is_etf(symbol):
            return self.etf_slippage_bps
        if traded_amount is None or traded_amount <= 0:
            return self.slippage_bps
        if traded_amount <= self.low_liquidity_amount:
            return max(self.slippage_bps, self.low_liquidity_slippage_bps)
        if traded_amount <= self.mid_liquidity_amount:
            return max(self.slippage_bps, self.mid_liquidity_slippage_bps)
        return self.slippage_bps


def _execution_params() -> dict[str, object]:
    try:
        return get_backtest_execution()
    except Exception:
        return {}


def _float_param(params: dict[str, object], key: str, fallback: float) -> float:
    try:
        return float(params.get(key, fallback))
    except (TypeError, ValueError):
        return fallback
