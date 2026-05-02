from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    LowBuyStrategyPerformanceSnapshot,
    LowBuyStrategyPerformanceWindowSnapshot,
)


class LowBuyPerformanceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def fetch(
        self,
        latest_trade_date: str,
        strategy_key: str,
        lookback_days: int,
    ) -> LowBuyStrategyPerformanceWindowSnapshot | LowBuyStrategyPerformanceSnapshot | None:
        row = (
            self.db.execute(
                select(LowBuyStrategyPerformanceWindowSnapshot).where(
                    LowBuyStrategyPerformanceWindowSnapshot.latest_trade_date == latest_trade_date,
                    LowBuyStrategyPerformanceWindowSnapshot.strategy_key == strategy_key,
                    LowBuyStrategyPerformanceWindowSnapshot.lookback_days == lookback_days,
                )
            )
            .scalars()
            .first()
        )
        if row is not None:
            return row
        if lookback_days != 60:
            return None
        return (
            self.db.execute(
                select(LowBuyStrategyPerformanceSnapshot).where(
                    LowBuyStrategyPerformanceSnapshot.latest_trade_date == latest_trade_date,
                    LowBuyStrategyPerformanceSnapshot.strategy_key == strategy_key,
                )
            )
            .scalars()
            .first()
        )

    def save(
        self,
        latest_trade_date: str,
        strategy_key: str,
        lookback_days: int,
        values: dict[str, object],
    ) -> None:
        window_values = dict(values)
        window_values.pop("lookback_days", None)
        row = (
            self.db.execute(
                select(LowBuyStrategyPerformanceWindowSnapshot).where(
                    LowBuyStrategyPerformanceWindowSnapshot.latest_trade_date == latest_trade_date,
                    LowBuyStrategyPerformanceWindowSnapshot.strategy_key == strategy_key,
                    LowBuyStrategyPerformanceWindowSnapshot.lookback_days == lookback_days,
                )
            )
            .scalars()
            .first()
        )
        if row is None:
            self.db.add(
                LowBuyStrategyPerformanceWindowSnapshot(
                    latest_trade_date=latest_trade_date,
                    strategy_key=strategy_key,
                    lookback_days=lookback_days,
                    **window_values,
                )
            )
        else:
            for key, value in window_values.items():
                setattr(row, key, value)

        if lookback_days != 60:
            return

        legacy_row = (
            self.db.execute(
                select(LowBuyStrategyPerformanceSnapshot).where(
                    LowBuyStrategyPerformanceSnapshot.latest_trade_date == latest_trade_date,
                    LowBuyStrategyPerformanceSnapshot.strategy_key == strategy_key,
                )
            )
            .scalars()
            .first()
        )
        legacy_values = dict(values)
        legacy_values["lookback_days"] = lookback_days
        if legacy_row is None:
            self.db.add(
                LowBuyStrategyPerformanceSnapshot(
                    latest_trade_date=latest_trade_date,
                    strategy_key=strategy_key,
                    **legacy_values,
                )
            )
            return
        for key, value in legacy_values.items():
            setattr(legacy_row, key, value)
