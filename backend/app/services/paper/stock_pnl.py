from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import PaperAccount, PaperOrder, PaperPosition, PaperTrade
from app.services.paper.ledger_replay import ReplaySymbolLedger, replay_trades


ZERO = Decimal("0")


class PaperStockPnlService:
    """Build exact per-symbol paper PnL from full trade history."""

    def __init__(self, db: Session):
        self.db = db

    def summarize(self, account_id: int) -> list[dict]:
        ledgers = self._replay_trades(account_id)
        self._apply_current_positions(account_id, ledgers)
        return [
            self._to_payload(ledger)
            for ledger in sorted(ledgers.values(), key=lambda row: (row.current_quantity <= 0, row.symbol))
        ]

    def summary(self, account_id: int) -> dict:
        account = self.db.get(PaperAccount, account_id)
        items = self.summarize(account_id)
        stock_total_pnl = sum(item["total_pnl"] for item in items)
        realized_pnl = sum(item["realized_pnl"] for item in items)
        unrealized_pnl = sum(item["unrealized_pnl"] for item in items)
        account_total_pnl = (
            _float(_decimal(account.total_assets) - _decimal(account.initial_cash))
            if account is not None
            else 0.0
        )
        return {
            "items": items,
            "summary": {
                "item_count": len(items),
                "account_total_pnl": account_total_pnl,
                "stock_total_pnl": round(stock_total_pnl, 2),
                "realized_pnl": round(realized_pnl, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "reconciliation_gap": round(account_total_pnl - stock_total_pnl, 2),
            },
        }

    def _replay_trades(self, account_id: int) -> dict[str, ReplaySymbolLedger]:
        rows = (
            self.db.execute(
                select(PaperTrade, PaperOrder.name)
                .join(PaperOrder, PaperOrder.id == PaperTrade.order_id, isouter=True)
                .where(PaperTrade.account_id == account_id)
                .order_by(PaperTrade.trade_time.asc(), PaperTrade.id.asc())
            )
            .all()
        )
        return replay_trades(rows).ledgers

    def _apply_current_positions(self, account_id: int, ledgers: dict[str, ReplaySymbolLedger]) -> None:
        positions = (
            self.db.execute(select(PaperPosition).where(PaperPosition.account_id == account_id).order_by(PaperPosition.symbol.asc()))
            .scalars()
            .all()
        )
        for row in positions:
            ledger = ledgers.setdefault(row.symbol, ReplaySymbolLedger(symbol=row.symbol, name=row.name or row.symbol))
            ledger.name = row.name or ledger.name or row.symbol
            ledger.current_quantity = int(row.quantity or 0)
            ledger.avg_cost = _decimal(row.cost_basis) if row.cost_basis is not None else ledger.avg_cost
            ledger.unrealized_pnl = _decimal(row.unrealized_pnl)

    def _to_payload(self, ledger: ReplaySymbolLedger) -> dict:
        return {
            "symbol": ledger.symbol,
            "name": ledger.name or ledger.symbol,
            "buy_quantity": ledger.buy_quantity,
            "sell_quantity": ledger.sell_quantity,
            "current_quantity": ledger.current_quantity,
            "avg_cost": _float_or_none(ledger.avg_cost),
            "realized_pnl": _float(ledger.realized_pnl),
            "unrealized_pnl": _float(ledger.unrealized_pnl),
            "total_pnl": _float(ledger.realized_pnl + ledger.unrealized_pnl),
            "total_fees": _float(ledger.total_fees),
            "replay_complete": ledger.replay_complete,
        }


def _decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def _float(value: Decimal) -> float:
    return round(float(value), 2)


def _float_or_none(value: Decimal | None) -> float | None:
    return None if value is None else _float(value)
