from __future__ import annotations

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.models.entities import LowBuyStrategyPoolSnapshot


class LowBuyStrategyPoolRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def fetch(
        self,
        *,
        latest_trade_date: str,
        pool_key: str,
        strategy_key: str,
    ) -> list[LowBuyStrategyPoolSnapshot]:
        return (
            self.db.execute(
                select(LowBuyStrategyPoolSnapshot)
                .where(
                    LowBuyStrategyPoolSnapshot.latest_trade_date == latest_trade_date,
                    LowBuyStrategyPoolSnapshot.pool_key == pool_key,
                    LowBuyStrategyPoolSnapshot.strategy_key == strategy_key,
                )
                .order_by(
                    LowBuyStrategyPoolSnapshot.rank_score.desc(),
                    LowBuyStrategyPoolSnapshot.amount.desc(),
                )
            )
            .scalars()
            .all()
        )

    def fetch_recent_dates(
        self,
        *,
        latest_trade_date: str,
        pool_key: str,
        strategy_key: str,
        limit: int = 6,
    ) -> list[str]:
        return [
            str(item)
            for item in self.db.execute(
                select(LowBuyStrategyPoolSnapshot.latest_trade_date)
                .where(
                    LowBuyStrategyPoolSnapshot.latest_trade_date <= latest_trade_date,
                    LowBuyStrategyPoolSnapshot.pool_key == pool_key,
                    LowBuyStrategyPoolSnapshot.strategy_key == strategy_key,
                )
                .distinct()
                .order_by(desc(LowBuyStrategyPoolSnapshot.latest_trade_date))
                .limit(max(1, limit))
            )
            .scalars()
            .all()
        ]

    def replace(
        self,
        *,
        latest_trade_date: str,
        pool_key: str,
        strategy_key: str,
        rows: list[LowBuyStrategyPoolSnapshot],
    ) -> None:
        self.db.execute(
            delete(LowBuyStrategyPoolSnapshot).where(
                LowBuyStrategyPoolSnapshot.latest_trade_date == latest_trade_date,
                LowBuyStrategyPoolSnapshot.pool_key == pool_key,
                LowBuyStrategyPoolSnapshot.strategy_key == strategy_key,
            )
        )
        for row in rows:
            self.db.add(row)
