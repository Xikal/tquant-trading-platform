from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.entities import LowBuyCloseReviewSnapshot


class LowBuyCloseReviewRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def fetch(self, latest_trade_date: str, strategy_key: str) -> list[LowBuyCloseReviewSnapshot]:
        return (
            self.db.execute(
                select(LowBuyCloseReviewSnapshot)
                .where(
                    LowBuyCloseReviewSnapshot.latest_trade_date == latest_trade_date,
                    LowBuyCloseReviewSnapshot.strategy_key == strategy_key,
                )
                .order_by(
                    LowBuyCloseReviewSnapshot.signal_state.asc(),
                    LowBuyCloseReviewSnapshot.updated_at.desc(),
                    LowBuyCloseReviewSnapshot.symbol.asc(),
                )
            )
            .scalars()
            .all()
        )

    def replace(
        self,
        latest_trade_date: str,
        strategy_key: str,
        rows: list[LowBuyCloseReviewSnapshot],
    ) -> None:
        self.db.execute(
            delete(LowBuyCloseReviewSnapshot).where(
                LowBuyCloseReviewSnapshot.latest_trade_date == latest_trade_date,
                LowBuyCloseReviewSnapshot.strategy_key == strategy_key,
            )
        )
        for row in rows:
            self.db.add(row)
