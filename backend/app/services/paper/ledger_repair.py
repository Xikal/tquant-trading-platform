from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.entities import (
    PaperAccount,
    PaperDailyReport,
    PaperMarketPerfDaily,
    PaperOrder,
    PaperPerformanceSnapshot,
    PaperPosition,
    PaperPositionLot,
    PaperStrategyPerfDaily,
    PaperTrade,
    PaperTradeTag,
)
from app.core.timezone import beijing_today
from app.services.market.trading_calendar import last_a_share_trading_day, next_a_share_trading_day
from app.services.paper.account import PaperAccountService
from app.services.paper.ledger_replay import ReplayResult, ReplayTradeIssue, replay_trades
from app.services.paper.money import ZERO, to_decimal
from app.services.paper.position import PaperPositionService
from app.services.paper.symbols import is_etf

logger = logging.getLogger(__name__)


@dataclass
class PaperLedgerRepairResult:
    account_id: int
    applied: bool
    issue_count: int
    corrected_cash_available: Decimal
    corrected_realized_pnl: Decimal
    corrected_market_value: Decimal
    corrected_total_assets: Decimal
    reconciliation_gap_before: Decimal
    reconciliation_gap_after: Decimal
    issues: list[dict]


@dataclass
class _RebuildLot:
    symbol: str
    quantity: int
    remaining: int
    total_cost: Decimal
    available_date: date
    source_order_id: int | None


@dataclass
class _RebuildPosition:
    symbol: str
    name: str
    strategy_keys: set[str]
    lots: list[_RebuildLot]

    @property
    def quantity(self) -> int:
        return sum(lot.remaining for lot in self.lots)


class PaperLedgerRepairService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.accounts = PaperAccountService(db)
        self.positions = PaperPositionService(db)

    def preview(self, account_id: int) -> PaperLedgerRepairResult:
        account = self.accounts.get_account(account_id)
        replay = self._replay(account_id)
        market_value = self._current_market_value(account_id)
        corrected_cash = to_decimal(account.initial_cash) + replay.corrected_cash_delta
        corrected_total = corrected_cash + market_value
        before_gap = to_decimal(account.total_assets) - (corrected_cash + market_value)
        return self._build_result(
            account=account,
            replay=replay,
            applied=False,
            corrected_cash=corrected_cash,
            corrected_market_value=market_value,
            corrected_total=corrected_total,
            before_gap=before_gap,
            after_gap=ZERO,
        )

    def apply(self, account_id: int) -> PaperLedgerRepairResult:
        try:
            account = self.accounts.get_account(account_id, for_update=True)
            replay = self._replay(account_id)
            latest_prices = self._latest_price_snapshot(account_id)
            before_gap = to_decimal(account.total_assets) - (
                to_decimal(account.initial_cash) + replay.corrected_cash_delta + self._current_market_value(account_id)
            )
            self._apply_trade_repairs(replay.issues)
            self._rebuild_account_state(account)
            self._replay_into_account(account_id)
            if latest_prices:
                self.positions.refresh_quotes(account_id, latest_prices)
            else:
                logger.warning(
                    "ledger repair account %s uses DB price snapshot only; no usable latest_price found before replay",
                    account_id,
                )
            account = self.accounts.update_market_value(account_id)
            self.db.flush()
            after_gap = self._account_reconciliation_gap(account)
            if abs(after_gap) > Decimal("0.01"):
                raise RuntimeError(f"账本修复后对账差额仍为 {after_gap}")
            result = self._build_result(
                account=account,
                replay=replay,
                applied=True,
                corrected_cash=to_decimal(account.cash_available),
                corrected_market_value=to_decimal(account.market_value),
                corrected_total=to_decimal(account.total_assets),
                before_gap=before_gap,
                after_gap=after_gap,
            )
            self.db.commit()
            return result
        except Exception as exc:
            self.db.rollback()
            raise RuntimeError(f"账本修复失败，已回滚: {exc}") from exc

    def _replay(self, account_id: int) -> ReplayResult:
        rows = (
            self.db.execute(
                select(PaperTrade, PaperOrder.name)
                .join(PaperOrder, PaperOrder.id == PaperTrade.order_id, isouter=True)
                .where(PaperTrade.account_id == account_id)
                .order_by(PaperTrade.trade_time.asc(), PaperTrade.id.asc())
            )
            .all()
        )
        return replay_trades(rows)

    def _apply_trade_repairs(self, issues: list[ReplayTradeIssue]) -> None:
        for issue in issues:
            trade = self.db.get(PaperTrade, issue.trade_id)
            order = self.db.get(PaperOrder, issue.order_id)
            if trade is None:
                continue
            if issue.valid_quantity <= 0:
                self.db.execute(delete(PaperTradeTag).where(PaperTradeTag.trade_id == trade.id))
                self.db.delete(trade)
                if order is not None:
                    order.status = "rejected"
                    order.filled_quantity = 0
                    order.avg_fill_price = None
                    order.reject_reason = "ledger_repair: 卖出数量超过可用持仓，已剔除异常成交"
                continue
            ratio = Decimal(issue.valid_quantity) / Decimal(issue.original_quantity)
            trade.quantity = issue.valid_quantity
            trade.gross_amount = _scaled_money(trade.gross_amount, ratio)
            trade.commission = _scaled_fee(trade.commission, ratio)
            trade.stamp_tax = _scaled_fee(trade.stamp_tax, ratio)
            trade.transfer_fee = _scaled_fee(trade.transfer_fee, ratio)
            trade.net_amount = _scaled_money(trade.net_amount, ratio)
            if order is not None:
                order.filled_quantity = issue.valid_quantity
                order.status = "partial"
                order.reject_reason = "ledger_repair: 部分卖出超出可用持仓，已按有效数量修正"

    def _rebuild_account_state(self, account: PaperAccount) -> None:
        account.cash_available = account.initial_cash
        account.frozen_cash = ZERO
        account.market_value = ZERO
        account.total_assets = account.initial_cash
        account.realized_pnl = ZERO
        account.unrealized_pnl = ZERO
        self.db.execute(delete(PaperPositionLot).where(PaperPositionLot.account_id == account.id))
        self.db.execute(delete(PaperPosition).where(PaperPosition.account_id == account.id))
        self.db.execute(delete(PaperPerformanceSnapshot).where(PaperPerformanceSnapshot.account_id == account.id))
        self.db.execute(delete(PaperStrategyPerfDaily).where(PaperStrategyPerfDaily.account_id == account.id))
        self.db.execute(delete(PaperMarketPerfDaily).where(PaperMarketPerfDaily.account_id == account.id))
        self.db.execute(delete(PaperDailyReport).where(PaperDailyReport.account_id == account.id))
        self.db.flush()

    def _replay_into_account(self, account_id: int) -> None:
        account = self.accounts.get_account(account_id, for_update=True)
        trades = (
            self.db.execute(
                select(PaperTrade)
                .where(PaperTrade.account_id == account_id)
                .order_by(PaperTrade.trade_time.asc(), PaperTrade.id.asc())
            )
            .scalars()
            .all()
        )
        positions: dict[str, _RebuildPosition] = {}
        for trade in trades:
            qty = int(trade.quantity or 0)
            if qty <= 0:
                continue
            if trade.side == "buy":
                account.cash_available = to_decimal(account.cash_available) - to_decimal(trade.net_amount)
                position = positions.setdefault(
                    trade.symbol,
                    _RebuildPosition(
                        symbol=trade.symbol,
                        name=self._order_name(trade.order_id, trade.symbol),
                        strategy_keys=set(),
                        lots=[],
                    ),
                )
                if trade.strategy_key:
                    position.strategy_keys.add(trade.strategy_key)
                position.lots.append(
                    _RebuildLot(
                        symbol=trade.symbol,
                        quantity=qty,
                        remaining=qty,
                        total_cost=to_decimal(trade.net_amount),
                        available_date=_available_date_for_trade(trade.symbol, _trade_date(trade)),
                        source_order_id=trade.order_id,
                    )
                )
                continue
            position = positions.get(trade.symbol)
            if position is None:
                raise ValueError(f"重算失败：{trade.symbol} 历史卖出前不存在可重建持仓。")
            realized_cost = self._consume_position_cost(position, qty)
            account.cash_available = to_decimal(account.cash_available) + to_decimal(trade.net_amount)
            account.realized_pnl = to_decimal(account.realized_pnl) + (
                to_decimal(trade.net_amount) - realized_cost
            )
        self._persist_rebuilt_positions(account_id, positions)

    def _latest_price_snapshot(self, account_id: int) -> dict[str, Decimal]:
        """Return DB snapshot prices only.

        This intentionally uses the latest persisted PaperPosition.latest_price
        values, not live quotes. If the quote refresh job is stale these prices
        may be old, so callers should treat them as a best-effort valuation
        fallback and log accordingly before applying the repair.
        """
        rows = (
            self.db.execute(select(PaperPosition).where(PaperPosition.account_id == account_id))
            .scalars()
            .all()
        )
        snapshot = {
            row.symbol: to_decimal(row.latest_price)
            for row in rows
            if row.latest_price is not None and to_decimal(row.latest_price) > ZERO
        }
        if len(snapshot) < len(rows):
            logger.warning(
                "ledger repair account %s found %s/%s positions with usable DB snapshot prices",
                account_id,
                len(snapshot),
                len(rows),
            )
        return snapshot

    def _current_market_value(self, account_id: int) -> Decimal:
        rows = (
            self.db.execute(select(PaperPosition.market_value).where(PaperPosition.account_id == account_id))
            .scalars()
            .all()
        )
        return sum((to_decimal(value) for value in rows), ZERO)

    def _consume_position_cost(self, position: _RebuildPosition, quantity: int) -> Decimal:
        remaining = quantity
        total_cost = ZERO
        for lot in position.lots:
            if remaining <= 0:
                break
            used = min(remaining, lot.remaining)
            if used <= 0:
                continue
            if used == lot.remaining:
                consumed_cost = lot.total_cost
            else:
                consumed_cost = lot.total_cost * Decimal(used) / Decimal(lot.remaining)
            total_cost += consumed_cost
            lot.total_cost -= consumed_cost
            lot.remaining -= used
            remaining -= used
        if remaining > 0:
            raise ValueError("重算失败：历史批次不足，无法回放卖出记录。")
        return total_cost.quantize(Decimal("0.01"))

    def _persist_rebuilt_positions(self, account_id: int, positions: dict[str, _RebuildPosition]) -> None:
        sell_as_of = last_a_share_trading_day(beijing_today())
        for position in positions.values():
            quantity = position.quantity
            if quantity <= 0:
                continue
            total_cost = sum(lot.total_cost for lot in position.lots if lot.remaining > 0)
            cost_basis = (total_cost / Decimal(quantity)).quantize(Decimal("0.0001")) if quantity > 0 else ZERO
            available_quantity = sum(
                lot.remaining
                for lot in position.lots
                if lot.remaining > 0 and (beijing_today() if is_etf(position.symbol) else sell_as_of) >= lot.available_date
            )
            row = PaperPosition(
                account_id=account_id,
                symbol=position.symbol,
                name=position.name,
                quantity=quantity,
                available_quantity=available_quantity,
                cost_basis=cost_basis,
                strategy_sources=_strategy_sources_json(position.strategy_keys),
            )
            self.db.add(row)
            self.db.flush()
            for lot in position.lots:
                if lot.remaining <= 0:
                    continue
                self.db.add(
                    PaperPositionLot(
                        account_id=account_id,
                        position_id=row.id,
                        symbol=position.symbol,
                        quantity=lot.quantity,
                        remaining=lot.remaining,
                        available_date=lot.available_date,
                        cost_price=(lot.total_cost / Decimal(max(lot.remaining, 1))).quantize(Decimal("0.0001")),
                        source_order_id=lot.source_order_id,
                    )
                )

    def _build_result(
        self,
        *,
        account: PaperAccount,
        replay: ReplayResult,
        applied: bool,
        corrected_cash: Decimal,
        corrected_market_value: Decimal,
        corrected_total: Decimal,
        before_gap: Decimal,
        after_gap: Decimal,
    ) -> PaperLedgerRepairResult:
        return PaperLedgerRepairResult(
            account_id=account.id,
            applied=applied,
            issue_count=len(replay.issues),
            corrected_cash_available=corrected_cash,
            corrected_realized_pnl=replay.corrected_realized_pnl if not applied else to_decimal(account.realized_pnl),
            corrected_market_value=corrected_market_value,
            corrected_total_assets=corrected_total,
            reconciliation_gap_before=before_gap.quantize(Decimal("0.01")),
            reconciliation_gap_after=after_gap.quantize(Decimal("0.01")),
            issues=[_issue_payload(issue) for issue in replay.issues],
        )

    def _order_name(self, order_id: int, default_symbol: str) -> str:
        order = self.db.get(PaperOrder, order_id)
        return order.name if order and order.name else default_symbol

    def _account_reconciliation_gap(self, account: PaperAccount) -> Decimal:
        total_pnl = (
            to_decimal(account.total_assets)
            - to_decimal(account.initial_cash)
        )
        detail_pnl = to_decimal(account.realized_pnl) + to_decimal(account.unrealized_pnl)
        return (total_pnl - detail_pnl).quantize(Decimal("0.01"))


def _issue_payload(issue) -> dict:
    return {
        "trade_id": issue.trade_id,
        "order_id": issue.order_id,
        "symbol": issue.symbol,
        "side": issue.side,
        "original_quantity": issue.original_quantity,
        "valid_quantity": issue.valid_quantity,
        "invalid_quantity": issue.invalid_quantity,
        "reason": issue.reason,
    }


def _scaled_money(value, ratio: Decimal) -> Decimal:
    return (to_decimal(value) * ratio).quantize(Decimal("0.01"))


def _scaled_fee(value, ratio: Decimal) -> Decimal:
    return (to_decimal(value) * ratio).quantize(Decimal("0.0001"))


def _trade_date(trade: PaperTrade) -> date:
    return trade.trade_time.date()


def _available_date_for_trade(symbol: str, trade_date: date) -> date:
    return trade_date if is_etf(symbol) else next_a_share_trading_day(trade_date)


def _strategy_sources_json(values: set[str]) -> str:
    keys = sorted(value for value in values if value)
    if not keys:
        return "[]"
    return "[" + ",".join(f'"{key}"' for key in keys) + "]"
