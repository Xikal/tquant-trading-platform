from __future__ import annotations

from datetime import date
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import TickTradeSnapshot


class TickTradeSnapshotStore:
    def __init__(self, db: Session):
        self.db = db

    def list_ticks(
        self,
        *,
        symbol: str,
        trade_date: date,
        source: str | None = None,
        limit: int = 10000,
    ) -> list[TickTradeSnapshot]:
        query = select(TickTradeSnapshot).where(
            TickTradeSnapshot.symbol == symbol,
            TickTradeSnapshot.trade_date == trade_date,
        )
        if source:
            query = query.where(TickTradeSnapshot.source == source)
        query = query.order_by(TickTradeSnapshot.trade_timestamp.asc()).limit(limit)
        return list(self.db.execute(query).scalars().all())

    def persist(self, rows: Iterable[TickTradeSnapshot]) -> int:
        count = 0
        for row in rows:
            self.db.add(row)
            count += 1
        if count:
            self.db.commit()
        return count
