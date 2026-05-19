from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import PaperAccount, PaperOrder, PaperPosition, PaperTrade, RiskEvent
from app.core.timezone import beijing_today
from app.services.low_buy.strategy_parameter_defaults_parts.runtime import PAPER_RISK_CONTROL_DEFAULTS
from app.services.quant.runtime_parameters import get_paper_risk_control
from app.services.shared.trading_costs import round_trip_fee_pct


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
        params = _risk_params()
        account = self._account(account_id)
        total_assets = self._total_assets(account)
        order_value = estimated_price * Decimal(max(quantity, 0))
        max_single_order_pct = _fraction_param(params, "max_single_order_pct")
        max_single_symbol_pct = _pct_param(params, "max_single_symbol_position_pct")
        max_daily_buy_pct = _pct_param(params, "max_daily_buy_pct")
        max_daily_order_count = int(_numeric_param(params, "max_daily_order_count"))
        fee_warning_pct = _numeric_param(params, "fee_warning_pct")
        fee_block_pct = _numeric_param(params, "fee_block_pct")
        max_order_value = total_assets * max_single_order_pct
        daily_order_count = self._daily_order_count(account_id)
        existing_order_count = max(0, daily_order_count - 1) if current_order_counted else daily_order_count
        reasons: list[str] = []
        warnings: list[str] = []

        if account.status != "active":
            reasons.append("模拟账户已暂停，不能提交新委托。")
        open_risk = self._blocking_risk_event(account_id)
        if open_risk:
            reasons.append(open_risk)
        if existing_order_count >= max_daily_order_count:
            reasons.append(f"今日委托次数已达到 {max_daily_order_count} 次上限。")
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
                reasons.append(f"单笔买入金额超过账户资产 {_format_pct(_pct(max_single_order_pct))}，已拒绝。")
            if projected_pct > max_single_symbol_pct:
                reasons.append(f"买入后单只股票仓位会超过 {_format_pct(max_single_symbol_pct)}，已拒绝。")
            if daily_buy_used_pct > max_daily_buy_pct:
                reasons.append(f"今日累计买入金额会超过账户资产 {_format_pct(max_daily_buy_pct)}，已拒绝。")
        elif side != "sell":
            reasons.append("委托方向只能是 buy 或 sell。")

        fee_pct = round_trip_fee_pct(symbol=symbol, side=side, price=estimated_price, quantity=quantity)
        if fee_pct > fee_block_pct:
            reasons.append(f"交易摩擦约 {fee_pct:.2f}%，超过 {fee_block_pct:.2f}%，小额委托已拒绝。")
        elif fee_pct > fee_warning_pct:
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
        params = _risk_params()
        total_assets = self._total_assets(account)
        return {
            "account_status": account.status,
            "total_assets": float(total_assets),
            "max_single_order_pct": _pct(_fraction_param(params, "max_single_order_pct")),
            "max_single_symbol_position_pct": _pct_param(params, "max_single_symbol_position_pct"),
            "max_daily_buy_pct": _pct_param(params, "max_daily_buy_pct"),
            "max_daily_order_count": int(_numeric_param(params, "max_daily_order_count")),
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
    today = beijing_today()
    start = datetime.combine(today, time.min)
    end = datetime.combine(today, time.max)
    return start, end


def _pct(value: Decimal) -> float:
    return float(value * Decimal("100"))


def _risk_params() -> dict[str, object]:
    values = {**PAPER_RISK_CONTROL_DEFAULTS}
    values.update(get_paper_risk_control())
    return values


def _numeric_param(params: dict[str, object], key: str) -> float:
    fallback = PAPER_RISK_CONTROL_DEFAULTS[key]
    try:
        value = float(params.get(key, fallback))
    except (TypeError, ValueError):
        value = float(fallback)
    return max(value, 0.0)


def _fraction_param(params: dict[str, object], key: str) -> Decimal:
    return Decimal(str(_pct_param(params, key))) / Decimal("100")


def _pct_param(params: dict[str, object], key: str) -> float:
    return min(_numeric_param(params, key), 100.0)


def _format_pct(value: float) -> str:
    return f"{value:.0f}%" if abs(value - round(value)) < 0.0001 else f"{value:.2f}%"
