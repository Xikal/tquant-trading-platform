from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.entities import WatchlistSignalSnapshot


class WatchlistSignalSnapshotRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def fetch_by_symbols(self, symbols: list[str]) -> list[WatchlistSignalSnapshot]:
        if not symbols:
            return []
        return (
            self.db.execute(
                select(WatchlistSignalSnapshot).where(WatchlistSignalSnapshot.symbol.in_(symbols))
            )
            .scalars()
            .all()
        )

    def upsert_many(self, payloads: dict[str, str]) -> None:
        if not payloads:
            return
        existing = {
            row.symbol: row
            for row in self.fetch_by_symbols(list(payloads))
        }
        for symbol, payload_json in payloads.items():
            row = existing.get(symbol)
            if row is None:
                self.db.add(WatchlistSignalSnapshot(symbol=symbol, payload_json=payload_json))
                continue
            row.payload_json = payload_json

    def delete_except(self, symbols: list[str]) -> None:
        if not symbols:
            self.db.execute(delete(WatchlistSignalSnapshot))
            return
        self.db.execute(delete(WatchlistSignalSnapshot).where(~WatchlistSignalSnapshot.symbol.in_(symbols)))

    def delete_symbol(self, symbol: str) -> None:
        self.db.execute(delete(WatchlistSignalSnapshot).where(WatchlistSignalSnapshot.symbol == symbol))
