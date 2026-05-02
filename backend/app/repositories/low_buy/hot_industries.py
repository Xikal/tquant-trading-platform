from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.entities import LowBuyHotIndustrySnapshot


class LowBuyHotIndustryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def fetch(self, latest_trade_date: str) -> LowBuyHotIndustrySnapshot | None:
        return (
            self.db.execute(
                select(LowBuyHotIndustrySnapshot).where(
                    LowBuyHotIndustrySnapshot.latest_trade_date == latest_trade_date
                )
            )
            .scalars()
            .first()
        )

    def fetch_latest_valid(self, latest_trade_date: str) -> LowBuyHotIndustrySnapshot | None:
        return (
            self.db.execute(
                select(LowBuyHotIndustrySnapshot)
                .where(LowBuyHotIndustrySnapshot.latest_trade_date <= latest_trade_date)
                .order_by(desc(LowBuyHotIndustrySnapshot.latest_trade_date))
            )
            .scalars()
            .first()
        )

    def fetch_recent_valids(
        self,
        latest_trade_date: str,
        limit: int = 3,
    ) -> list[LowBuyHotIndustrySnapshot]:
        return (
            self.db.execute(
                select(LowBuyHotIndustrySnapshot)
                .where(LowBuyHotIndustrySnapshot.latest_trade_date <= latest_trade_date)
                .order_by(desc(LowBuyHotIndustrySnapshot.latest_trade_date))
                .limit(max(limit, 1))
            )
            .scalars()
            .all()
        )

    def save(
        self,
        *,
        latest_trade_date: str,
        source: str,
        industries_json: str,
    ) -> LowBuyHotIndustrySnapshot:
        row = self.fetch(latest_trade_date)
        if row is None:
            row = LowBuyHotIndustrySnapshot(
                latest_trade_date=latest_trade_date,
                source=source,
                industries_json=industries_json,
            )
            self.db.add(row)
            return row
        row.source = source
        row.industries_json = industries_json
        return row
