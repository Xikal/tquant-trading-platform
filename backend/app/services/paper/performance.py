from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import PaperAccount, PaperPerformanceSnapshot, PaperTrade


class PaperPerformanceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def compute_overall(self, account_id: int) -> dict:
        account = self.db.get(PaperAccount, account_id)
        trades = self._trades(account_id)
        returns = [item.return_pct for item in self._paired_sell_return_records(account_id)]
        wins = [value for value in returns if value > 0]
        losses = [value for value in returns if value < 0]
        total = len(returns)
        gross_gains = sum(wins)
        gross_losses = abs(sum(losses))
        total_return_pct = 0.0
        if account is not None and float(account.initial_cash or 0) > 0:
            total_return_pct = (float(account.total_assets or 0) - float(account.initial_cash)) / float(account.initial_cash) * 100
        return {
            "total_return_pct": round(total_return_pct, 3),
            "max_drawdown_pct": float(getattr(account, "max_drawdown_pct", 0.0) or 0.0),
            "win_rate_pct": _rate(len(wins), total),
            "net_win_rate_pct": _rate(len(wins) - len(losses), total),
            "avg_trade_return_pct": round(sum(returns) / total, 3) if total else 0.0,
            "avg_win_pct": round(sum(wins) / len(wins), 3) if wins else 0.0,
            "avg_loss_pct": round(sum(losses) / len(losses), 3) if losses else 0.0,
            "profit_factor": round(gross_gains / gross_losses, 3) if gross_losses > 0 else None,
            "stop_loss_rate_pct": 0.0,
            "total_trades": len(trades),
            "avg_hold_days": 0.0,
            "win_loss_ratio": round((sum(wins) / len(wins)) / abs(sum(losses) / len(losses)), 3) if wins and losses else None,
        }

    def compute_by_strategy(self, account_id: int) -> list[dict]:
        return self._grouped(account_id, "strategy_key")

    def compute_by_market_state(self, account_id: int) -> list[dict]:
        return self._grouped(account_id, "market_state")

    def sell_return_records(self, account_id: int) -> list[SellReturnRecord]:
        return self._paired_sell_return_records(account_id)

    def create_daily_snapshot(self, account_id: int) -> PaperPerformanceSnapshot:
        account = self.db.get(PaperAccount, account_id)
        if account is None:
            raise LookupError("模拟账户不存在")
        overall = self.compute_overall(account_id)
        today = date.today()
        row = self.db.execute(
            select(PaperPerformanceSnapshot).where(
                PaperPerformanceSnapshot.account_id == account_id,
                PaperPerformanceSnapshot.snapshot_date == today,
            )
        ).scalar_one_or_none()
        if row is None:
            row = PaperPerformanceSnapshot(account_id=account_id, snapshot_date=today)
            self.db.add(row)
        row.total_assets = account.total_assets
        row.cumulative_return_pct = overall["total_return_pct"]
        row.max_drawdown_pct = overall["max_drawdown_pct"]
        row.win_rate_pct = overall["win_rate_pct"]
        row.net_win_rate_pct = overall["net_win_rate_pct"]
        row.profit_factor = overall["profit_factor"]
        row.stop_loss_rate_pct = overall["stop_loss_rate_pct"]
        row.trade_count = overall["total_trades"]
        self.db.commit()
        self.db.refresh(row)
        return row

    def _grouped(self, account_id: int, field: str) -> list[dict]:
        buckets: dict[str, list[float]] = defaultdict(list)
        for item in self._paired_sell_return_records(account_id):
            buckets[item.group_key(field)].append(item.return_pct)
        result = []
        for key, values in buckets.items():
            wins = [value for value in values if value > 0]
            losses = [value for value in values if value < 0]
            gross_gains = sum(wins)
            gross_losses = abs(sum(losses))
            result.append(
                {
                    "key": key,
                    "trades": len(values),
                    "win_rate_pct": _rate(len(wins), len(values)),
                    "net_win_rate_pct": _rate(len(wins) - len(losses), len(values)),
                    "avg_return_pct": round(sum(values) / max(len(values), 1), 3),
                    "profit_factor": round(gross_gains / gross_losses, 3) if gross_losses > 0 else None,
                }
            )
        return result

    def _paired_sell_return_records(self, account_id: int) -> list[SellReturnRecord]:
        trades = self._trades(account_id)
        avg_cost_by_symbol: dict[str, Decimal] = {}
        qty_by_symbol: dict[str, int] = {}
        returns: list[SellReturnRecord] = []
        for trade in trades:
            qty = int(trade.quantity or 0)
            price = Decimal(str(trade.price or 0))
            if trade.side == "buy":
                old_qty = qty_by_symbol.get(trade.symbol, 0)
                old_cost = avg_cost_by_symbol.get(trade.symbol, Decimal("0"))
                total_qty = old_qty + qty
                avg_cost_by_symbol[trade.symbol] = ((old_cost * old_qty) + (price * qty)) / max(total_qty, 1)
                qty_by_symbol[trade.symbol] = total_qty
                continue
            cost = avg_cost_by_symbol.get(trade.symbol, Decimal("0"))
            if cost > 0:
                returns.append(
                    SellReturnRecord(
                        return_pct=float((price - cost) / cost * 100),
                        strategy_key=trade.strategy_key or "未分类",
                        market_state=trade.market_state or "未分类",
                    )
                )
            qty_by_symbol[trade.symbol] = max(0, qty_by_symbol.get(trade.symbol, 0) - qty)
        return returns

    def _trades(self, account_id: int) -> list[PaperTrade]:
        return (
            self.db.execute(select(PaperTrade).where(PaperTrade.account_id == account_id).order_by(PaperTrade.trade_time.asc()))
            .scalars()
            .all()
        )


def _rate(part: int, total: int) -> float:
    return round(part / total * 100, 3) if total > 0 else 0.0


@dataclass(frozen=True)
class SellReturnRecord:
    return_pct: float
    strategy_key: str
    market_state: str

    def group_key(self, field: str) -> str:
        if field == "strategy_key":
            return self.strategy_key or "未分类"
        if field == "market_state":
            return self.market_state or "未分类"
        return "未分类"
