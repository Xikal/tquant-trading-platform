from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import PaperOrder, PaperTrade
from app.services.market.board_exclusions import GROWTH_BOARD_REJECT_REASON, is_growth_board_stock
from app.services.paper.account import PaperAccountService
from app.services.paper.matching import MatchResult, OrderSide, OrderType, PaperMatchingEngine
from app.services.paper.money import to_decimal
from app.services.paper.order_idempotency import duplicate_auto_exit_exists
from app.services.paper.position import PaperPositionService
from app.services.paper.reasons import normalize_entry_reason, normalize_exit_reason
from app.services.paper.risk_control import PaperRiskControlService

logger = logging.getLogger(__name__)


class PaperOrderService:
    def __init__(self, db: Session, matching_engine: PaperMatchingEngine | None = None) -> None:
        self.db = db
        self.matching = matching_engine or PaperMatchingEngine()
        self.accounts = PaperAccountService(db)
        self.positions = PaperPositionService(db)
        self.risk = PaperRiskControlService(db)

    def create_order(
        self,
        *,
        account_id: int,
        symbol: str,
        name: str,
        side: str,
        order_type: str,
        quantity: int,
        price: Decimal | None,
        source: str,
        strategy_key: str,
        reason: str,
        signal_snapshot: dict,
        current_price: Decimal,
        quote_time: datetime,
        is_suspended: bool,
        up_limit: Decimal | None = None,
        down_limit: Decimal | None = None,
        intraday_confirmed: bool = True,
        commit: bool = True,
    ) -> PaperOrder:
        self.accounts.get_account(account_id, for_update=True)
        self._idempotency_check(account_id, symbol, side, source, signal_snapshot)
        self._precheck(account_id, symbol, side, quantity, current_price)
        self._risk_check(account_id, symbol, side, quantity, current_price)
        match = self.matching.match(
            symbol=symbol,
            side=OrderSide(side),
            order_type=OrderType(order_type),
            quantity=quantity,
            limit_price=price,
            current_price=current_price,
            quote_time=quote_time,
            is_suspended=is_suspended,
            up_limit=up_limit,
            down_limit=down_limit,
        )
        if match.result != MatchResult.FILLED or match.avg_fill_price is None or match.fee_detail is None:
            raise ValueError(match.reject_reason or "模拟委托未成交。")

        order = PaperOrder(
            account_id=account_id,
            symbol=symbol,
            name=name or symbol,
            side=side,
            order_type=order_type,
            price=price,
            quantity=quantity,
            source=source or "manual",
            strategy_key=strategy_key or "",
            reason=reason or "",
            signal_snapshot=json.dumps(signal_snapshot or {}, ensure_ascii=False),
        )
        self.db.add(order)
        self.db.flush()
        order.status = "filled"
        order.filled_quantity = match.filled_quantity
        order.avg_fill_price = match.avg_fill_price
        self._apply_trade(order, match.avg_fill_price, match.fee_detail.net_amount, match.fee_detail)
        if commit:
            self.db.commit()
            self.db.refresh(order)
        else:
            self.db.flush()
        return order

    def get_orders(
        self,
        *,
        account_id: int,
        symbol: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[PaperOrder]:
        statement = select(PaperOrder).where(PaperOrder.account_id == account_id)
        if symbol:
            statement = statement.where(PaperOrder.symbol == symbol)
        if status:
            statement = statement.where(PaperOrder.status == status)
        return self.db.execute(statement.order_by(PaperOrder.id.desc()).limit(limit)).scalars().all()

    def get_order(self, order_id: int) -> PaperOrder:
        order = self.db.get(PaperOrder, order_id)
        if order is None:
            raise LookupError("模拟委托不存在")
        return order

    def cancel_order(self, order_id: int) -> PaperOrder:
        order = self.get_order(order_id)
        if order.status not in {"pending", "partial"}:
            raise ValueError("只有未完全成交的委托可以撤销。")
        order.status = "cancelled"
        self.db.commit()
        self.db.refresh(order)
        return order

    def _precheck(self, account_id: int, symbol: str, side: str, quantity: int, current_price: Decimal) -> None:
        if quantity <= 0 or quantity % 100 != 0:
            raise ValueError("委托数量必须是 100 股整数倍。")
        if side == "buy":
            if is_growth_board_stock(symbol):
                raise ValueError(GROWTH_BOARD_REJECT_REASON)
            estimated = current_price * Decimal(quantity) + Decimal("20")
            if not self.accounts.check_balance_locked(account_id, estimated):
                raise ValueError("可用资金不足，模拟买入被拒绝。")
            return
        position = self.positions.get_position(account_id, symbol)
        if position is None or position.available_quantity < quantity:
            raise ValueError("可卖数量不足或当日买入未解锁，模拟卖出被拒绝。")

    def _risk_check(self, account_id: int, symbol: str, side: str, quantity: int, current_price: Decimal) -> None:
        decision = self.risk.check_order(
            account_id=account_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            estimated_price=current_price,
            current_order_counted=False,
        )
        if not decision.allowed:
            raise ValueError("；".join(decision.reasons))

    def _idempotency_check(
        self,
        account_id: int,
        symbol: str,
        side: str,
        source: str,
        signal_snapshot: dict,
    ) -> None:
        if duplicate_auto_exit_exists(
            self.db,
            account_id=account_id,
            symbol=symbol,
            side=side,
            source=source,
            signal_snapshot=signal_snapshot or {},
        ):
            raise ValueError("同一自动止损/时间退出委托今日已提交，已阻止重复平仓。")

    def _apply_trade(self, order: PaperOrder, fill_price: Decimal, net_amount: Decimal, fee_detail) -> None:
        account = self.accounts.get_account(order.account_id)
        entry_reason = normalize_entry_reason(order.reason, source=order.source).text if order.side == "buy" else ""
        exit_reason = normalize_exit_reason(_exit_reason_from_order(order), source=order.source).text
        cost_basis = Decimal("0")
        realized_pnl = Decimal("0")
        return_pct = Decimal("0")
        if order.side == "buy":
            account.cash_available = to_decimal(account.cash_available) - net_amount
            per_share_cost = net_amount / Decimal(order.filled_quantity)
            self.positions.add_position(
                account_id=order.account_id,
                symbol=order.symbol,
                name=order.name,
                quantity=order.filled_quantity,
                cost_price=per_share_cost,
                strategy_key=order.strategy_key,
                source_order_id=order.id,
            )
            self.positions.refresh_quotes(order.account_id, {order.symbol: fill_price})
        else:
            position = self.positions.get_position(order.account_id, order.symbol)
            cost_basis = to_decimal(position.cost_basis if position is not None else 0)
            self.positions.reduce_position(account_id=order.account_id, symbol=order.symbol, quantity=order.filled_quantity)
            self.positions.refresh_quotes(order.account_id, {order.symbol: fill_price})
            account.cash_available = to_decimal(account.cash_available) + net_amount
            realized_pnl = ((fill_price - cost_basis) * Decimal(order.filled_quantity)) - fee_detail.total_fee
            return_pct = ((fill_price / cost_basis) - Decimal("1")) * Decimal("100") if cost_basis > 0 else Decimal("0")
            account.realized_pnl = (
                to_decimal(account.realized_pnl)
                + realized_pnl
            )
        trade = PaperTrade(
            order_id=order.id,
            account_id=order.account_id,
            symbol=order.symbol,
            side=order.side,
            price=fill_price,
            quantity=order.filled_quantity,
            gross_amount=fee_detail.gross_amount,
            commission=fee_detail.commission,
            stamp_tax=fee_detail.stamp_tax,
            transfer_fee=fee_detail.transfer_fee,
            net_amount=net_amount,
            strategy_key=order.strategy_key,
            entry_reason=entry_reason[:240],
            exit_reason=exit_reason[:80],
        )
        self.db.add(trade)
        self.db.flush()
        if order.side == "sell":
            self._record_ml_trade_outcome(trade, cost_basis=cost_basis, realized_pnl=realized_pnl, return_pct=return_pct)
        self.accounts.update_market_value(order.account_id)

    def _record_ml_trade_outcome(
        self,
        trade: PaperTrade,
        *,
        cost_basis: Decimal,
        realized_pnl: Decimal,
        return_pct: Decimal,
    ) -> None:
        try:
            from app.services.ml_signal import MLSignalService

            MLSignalService(self.db).persist_paper_trade_outcome(
                trade,
                cost_basis=cost_basis,
                pnl_amount=realized_pnl,
                return_pct=return_pct,
                label_note="paper_trade_close",
            )
        except Exception:
            # ML sampling must not break deterministic paper order settlement.
            logger.warning("failed to persist ML paper-trade outcome", exc_info=True)
            return


def _exit_reason_from_order(order: PaperOrder) -> str:
    if order.side != "sell":
        return ""
    try:
        raw = json.loads(order.signal_snapshot or "{}")
    except Exception:
        raw = {}
    if isinstance(raw, dict):
        explicit = str(raw.get("exit_reason") or raw.get("reason") or "").strip()
        if explicit:
            return explicit
    reason = (order.reason or "").strip()
    return reason or "manual"
