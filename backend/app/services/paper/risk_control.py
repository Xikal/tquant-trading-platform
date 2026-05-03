from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import PaperAccount, PaperOrder, PaperPosition, PaperTrade, RiskEvent
from app.services.paper.fees import calculate_fee


MAX_SINGLE_ORDER_PCT = Decimal("0.30")
MAX_SINGLE_SYMBOL_POSITION_PCT = Decimal("0.40")
MAX_DAILY_BUY_PCT = Decimal("0.60")
MAX_DAILY_ORDER_COUNT = 20
FEE_WARNING_PCT = 1.00
FEE_BLOCK_PCT = 3.00


@dataclass(frozen=True)
class PaperRiskDecision:
    allowed: bool
    risk_level: str
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    max_single_order_value: float = 0.0
    projected_symbol_position_pct: float = 0.0
    daily_buy_used_pct: float = 0.0
    daily_order_count: int = 0


class PaperRiskControlService:
    """Pre-trade risk checks for paper trading.

    The service is deliberately deterministic and local: it does not call market
    data or strategy code, so it can be reused by Web/App/Agent paths safely.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def check_order(
        self,
        *,
        account_id: int,
        symbol: str,
        side: str,
        quantity: int,
        estimated_price: Decimal,
        current_order_counted: bool = False,
    ) -> PaperRiskDecision:
        account = self._account(account_id)
        total_assets = self._total_assets(account)
        order_value = estimated_price * Decimal(max(quantity, 0))
        max_order_value = total_assets * MAX_SINGLE_ORDER_PCT
        daily_order_count = self._daily_order_count(account_id)
        existing_order_count = max(0, daily_order_count - 1) if current_order_counted else daily_order_count
        reasons: list[str] = []
        warnings: list[str] = []

        if account.status != "active":
            reasons.append("模拟账户已暂停，不能提交新委托。")
        open_risk = self._blocking_risk_event(account_id)
        if open_risk:
            reasons.append(open_risk)
        if existing_order_count >= MAX_DAILY_ORDER_COUNT:
            reasons.append(f"今日委托次数已达到 {MAX_DAILY_ORDER_COUNT} 次上限。")
        if quantity <= 0 or quantity % 100 != 0:
            reasons.append("委托数量必须是 100 股整数倍。")

        projected_pct = self._projected_symbol_position_pct(
            account_id=account_id,
            symbol=symbol,
            side=side,
            order_value=order_value,
            total_assets=total_assets,
        )
        daily_buy_used_pct = self._daily_buy_used_pct(
            account_id=account_id,
            side=side,
            order_value=order_value,
            total_assets=total_assets,
        )

        if side == "buy":
            if order_value > max_order_value:
                reasons.append("单笔买入金额超过账户资产 30%，已拒绝。")
            if projected_pct > _pct(MAX_SINGLE_SYMBOL_POSITION_PCT):
                reasons.append("买入后单只股票仓位会超过 40%，已拒绝。")
            if daily_buy_used_pct > _pct(MAX_DAILY_BUY_PCT):
                reasons.append("今日累计买入金额会超过账户资产 60%，已拒绝。")
        elif side != "sell":
            reasons.append("委托方向只能是 buy 或 sell。")

        fee_pct = _round_trip_fee_pct(symbol=symbol, side=side, price=estimated_price, quantity=quantity)
        if fee_pct > FEE_BLOCK_PCT:
            reasons.append(f"交易摩擦约 {fee_pct:.2f}%，超过 3.00%，小额委托已拒绝。")
        elif fee_pct > FEE_WARNING_PCT:
            warnings.append(f"交易摩擦约 {fee_pct:.2f}%，小额委托会明显吞噬收益。")

        if not reasons and side == "buy" and projected_pct >= 30:
            warnings.append("买入后单只股票仓位较高，建议控制节奏。")

        return PaperRiskDecision(
            allowed=not reasons,
            risk_level="block" if reasons else ("note" if warnings else "normal"),
            reasons=reasons,
            warnings=warnings,
            max_single_order_value=float(max_order_value),
            projected_symbol_position_pct=round(projected_pct, 3),
            daily_buy_used_pct=round(daily_buy_used_pct, 3),
            daily_order_count=daily_order_count,
        )

    def account_status(self, account_id: int) -> dict:
        account = self._account(account_id)
        total_assets = self._total_assets(account)
        return {
            "account_status": account.status,
            "total_assets": float(total_assets),
            "max_single_order_pct": _pct(MAX_SINGLE_ORDER_PCT),
            "max_single_symbol_position_pct": _pct(MAX_SINGLE_SYMBOL_POSITION_PCT),
            "max_daily_buy_pct": _pct(MAX_DAILY_BUY_PCT),
            "max_daily_order_count": MAX_DAILY_ORDER_COUNT,
            "daily_order_count": self._daily_order_count(account_id),
            "daily_buy_used_pct": round(
                self._daily_buy_used_pct(
                    account_id=account_id,
                    side="hold",
                    order_value=Decimal("0"),
                    total_assets=total_assets,
                ),
                3,
            ),
        }

    def _account(self, account_id: int) -> PaperAccount:
        account = self.db.get(PaperAccount, account_id)
        if account is None:
            raise LookupError("模拟账户不存在")
        return account

    @staticmethod
    def _total_assets(account: PaperAccount) -> Decimal:
        raw_total = Decimal(str(account.total_assets or 0))
        raw_initial = Decimal(str(account.initial_cash or 0))
        return max(raw_total, raw_initial, Decimal("1"))

    def _projected_symbol_position_pct(
        self,
        *,
        account_id: int,
        symbol: str,
        side: str,
        order_value: Decimal,
        total_assets: Decimal,
    ) -> float:
        position_value = Decimal("0")
        row = self.db.execute(
            select(PaperPosition).where(PaperPosition.account_id == account_id, PaperPosition.symbol == symbol)
        ).scalar_one_or_none()
        if row is not None:
            position_value = Decimal(str(row.market_value or 0))
        projected = position_value + (order_value if side == "buy" else Decimal("0"))
        return float(projected / total_assets * Decimal("100"))

    def _daily_buy_used_pct(
        self,
        *,
        account_id: int,
        side: str,
        order_value: Decimal,
        total_assets: Decimal,
    ) -> float:
        used = self._daily_buy_amount(account_id)
        if side == "buy":
            used += order_value
        return float(used / total_assets * Decimal("100"))

    def _daily_buy_amount(self, account_id: int) -> Decimal:
        start, end = _today_window()
        amount = self.db.execute(
            select(func.coalesce(func.sum(PaperTrade.net_amount), 0)).where(
                PaperTrade.account_id == account_id,
                PaperTrade.side == "buy",
                PaperTrade.trade_time >= start,
                PaperTrade.trade_time < end,
            )
        ).scalar_one()
        return Decimal(str(amount or 0))

    def _daily_order_count(self, account_id: int) -> int:
        start, end = _today_window()
        count = self.db.execute(
            select(func.count(PaperOrder.id)).where(
                PaperOrder.account_id == account_id,
                PaperOrder.created_at >= start,
                PaperOrder.created_at < end,
            )
        ).scalar_one()
        return int(count or 0)

    def _blocking_risk_event(self, account_id: int) -> str:
        row = self.db.execute(
            select(RiskEvent).where(
                RiskEvent.account_id == account_id,
                RiskEvent.status == "open",
                RiskEvent.severity == "high",
            )
        ).scalar_one_or_none()
        if row is None:
            return ""
        return row.message or "账户存在高风险事件，已暂停新增委托。"


def _today_window() -> tuple[datetime, datetime]:
    today = datetime.now().date()
    start = datetime.combine(today, time.min)
    end = datetime.combine(today, time.max)
    return start, end


def _pct(value: Decimal) -> float:
    return float(value * Decimal("100"))


def _round_trip_fee_pct(*, symbol: str, side: str, price: Decimal, quantity: int) -> float:
    if price <= 0 or quantity <= 0:
        return 0.0
    gross = price * Decimal(quantity)
    if gross <= 0:
        return 0.0
    try:
        entry_side = "buy" if side == "buy" else "sell"
        exit_side = "sell" if entry_side == "buy" else "buy"
        current_fee = calculate_fee(symbol=symbol, side=entry_side, price=price, quantity=quantity).total_fee
        exit_fee = calculate_fee(symbol=symbol, side=exit_side, price=price, quantity=quantity).total_fee
    except Exception:
        return 0.0
    return float((current_fee + exit_fee) / gross * Decimal("100"))
