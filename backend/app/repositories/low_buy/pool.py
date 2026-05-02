from __future__ import annotations

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.models.entities import LowBuyPoolSnapshot


class LowBuyPoolRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def fetch(self, latest_trade_date: str) -> list[LowBuyPoolSnapshot]:
        return (
            self.db.execute(
                select(LowBuyPoolSnapshot)
                .where(LowBuyPoolSnapshot.latest_trade_date == latest_trade_date)
                .order_by(LowBuyPoolSnapshot.board_date.desc(), LowBuyPoolSnapshot.amount.desc())
            )
            .scalars()
            .all()
        )

    def fetch_recent_dates(self, latest_trade_date: str, limit: int = 6) -> list[str]:
        return [
            str(item)
            for item in self.db.execute(
                select(LowBuyPoolSnapshot.latest_trade_date)
                .where(LowBuyPoolSnapshot.latest_trade_date <= latest_trade_date)
                .distinct()
                .order_by(desc(LowBuyPoolSnapshot.latest_trade_date))
                .limit(max(1, limit))
            )
            .scalars()
            .all()
        ]

    def replace(self, latest_trade_date: str, rows: list[LowBuyPoolSnapshot]) -> None:
        self.db.execute(delete(LowBuyPoolSnapshot).where(LowBuyPoolSnapshot.latest_trade_date == latest_trade_date))
        for row in rows:
            self.db.add(row)
