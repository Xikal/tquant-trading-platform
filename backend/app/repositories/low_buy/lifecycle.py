from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import LowBuyTradeLifecycleSnapshot

PLAN_FIELDS = {
    "signal_trade_date",
    "strategy_key",
    "symbol",
    "name",
    "signal_state",
    "entry_plan_low",
    "entry_plan_high",
    "stop_loss",
    "take_profit",
    "max_holding_days",
    "payload_json",
}
EXECUTION_FIELDS = {
    "status",
    "entry_price",
    "entry_trade_date",
    "exit_price",
    "exit_trade_date",
    "exit_reason",
    "realized_return_pct",
    "max_gain_pct",
    "max_drawdown_pct",
    "attribution_note",
}
ACTIVE_STATUSES = {"entered", "holding"}


class LowBuyTradeLifecycleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def fetch_recent(
        self,
        *,
        strategy_key: str | None = None,
        limit: int = 100,
        user_scope: str = "default",
    ) -> list[LowBuyTradeLifecycleSnapshot]:
        statement = select(LowBuyTradeLifecycleSnapshot).where(
            LowBuyTradeLifecycleSnapshot.user_scope == user_scope
        )
        if strategy_key:
            statement = statement.where(LowBuyTradeLifecycleSnapshot.strategy_key == strategy_key)
        return (
            self.db.execute(
                statement.order_by(
                    LowBuyTradeLifecycleSnapshot.signal_trade_date.desc(),
                    LowBuyTradeLifecycleSnapshot.updated_at.desc(),
                ).limit(limit)
            )
            .scalars()
            .all()
        )

    def fetch_one(
        self,
        *,
        signal_trade_date: str,
        strategy_key: str,
        symbol: str,
        user_scope: str = "default",
    ) -> LowBuyTradeLifecycleSnapshot | None:
        return (
            self.db.execute(
                select(LowBuyTradeLifecycleSnapshot).where(
                    LowBuyTradeLifecycleSnapshot.user_scope == user_scope,
                    LowBuyTradeLifecycleSnapshot.signal_trade_date == signal_trade_date,
                    LowBuyTradeLifecycleSnapshot.strategy_key == strategy_key,
                    LowBuyTradeLifecycleSnapshot.symbol == symbol,
                )
            )
            .scalars()
            .first()
        )

    def upsert_planned(self, values: dict, user_scope: str = "default") -> LowBuyTradeLifecycleSnapshot:
        row = self.fetch_one(
            signal_trade_date=values["signal_trade_date"],
            strategy_key=values["strategy_key"],
            symbol=values["symbol"],
            user_scope=user_scope,
        )
        created = row is None
        if created:
            row = LowBuyTradeLifecycleSnapshot(user_scope=user_scope)
            self.db.add(row)
        editable_fields = set(values) if created else PLAN_FIELDS
        for key, value in values.items():
            if key not in editable_fields:
                continue
            setattr(row, key, value)
        if created:
            row.status = values.get("status", "planned")
        return row

    def update_execution(
        self,
        *,
        signal_trade_date: str,
        strategy_key: str,
        symbol: str,
        values: dict,
        user_scope: str = "default",
    ) -> LowBuyTradeLifecycleSnapshot | None:
        row = self.fetch_one(
            signal_trade_date=signal_trade_date,
            strategy_key=strategy_key,
            symbol=symbol,
            user_scope=user_scope,
        )
        if row is None:
            return None
        for key, value in values.items():
            if key not in EXECUTION_FIELDS or value is None:
                continue
            setattr(row, key, value)
        return row

    def fetch_active(
        self,
        *,
        limit: int = 300,
        user_scope: str = "default",
    ) -> list[LowBuyTradeLifecycleSnapshot]:
        return (
            self.db.execute(
                select(LowBuyTradeLifecycleSnapshot)
                .where(
                    LowBuyTradeLifecycleSnapshot.user_scope == user_scope,
                    LowBuyTradeLifecycleSnapshot.status.in_(ACTIVE_STATUSES),
                )
                .order_by(
                    LowBuyTradeLifecycleSnapshot.signal_trade_date.desc(),
                    LowBuyTradeLifecycleSnapshot.updated_at.desc(),
                )
                .limit(limit)
            )
            .scalars()
            .all()
        )
