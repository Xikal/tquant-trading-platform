from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import DailyBarSnapshot


@dataclass
class DailyBarRow:
    trade_date: str
    open_price: float
    close_price: float
    high_price: float
    low_price: float
    volume: float
    amount: float
    pct_chg: float


class DailyHistoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def latest_trade_date_for_symbol(self, symbol: str) -> str | None:
        row = (
            self.db.execute(
                select(DailyBarSnapshot.trade_date)
                .where(DailyBarSnapshot.symbol == symbol)
                .order_by(DailyBarSnapshot.trade_date.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        return str(row) if row else None

    def fetch_recent_trade_dates(self, count: int) -> list[str]:
        rows = (
            self.db.execute(
                select(DailyBarSnapshot.trade_date)
                .distinct()
                .order_by(DailyBarSnapshot.trade_date.desc())
                .limit(max(1, count))
            )
            .scalars()
            .all()
        )
        return sorted(str(row) for row in rows)

    def latest_complete_trade_date(
        self,
        *,
        max_trade_date: str | None = None,
        min_stock_count: int = 4500,
    ) -> str | None:
        query = select(
            DailyBarSnapshot.trade_date,
            func.count(DailyBarSnapshot.symbol).label("stock_count"),
        ).where(DailyBarSnapshot.instrument_type == "stock")
        if max_trade_date:
            query = query.where(DailyBarSnapshot.trade_date <= max_trade_date)
        rows = (
            self.db.execute(
                query.group_by(DailyBarSnapshot.trade_date)
                .order_by(DailyBarSnapshot.trade_date.desc())
                .limit(60)
            )
            .all()
        )
        for trade_date, stock_count in rows:
            if int(stock_count or 0) >= min_stock_count:
                return str(trade_date)
        return None

    def stock_count_by_trade_date(self, trade_date: str) -> int:
        return int(
            self.db.execute(
                select(func.count(DailyBarSnapshot.symbol)).where(
                    DailyBarSnapshot.trade_date == trade_date,
                    DailyBarSnapshot.instrument_type == "stock",
                )
            ).scalar_one()
            or 0
        )

    def fetch_rows(self, symbol: str, start_date_iso: str, latest_trade_date: str) -> list[DailyBarRow]:
        rows = (
            self.db.execute(
                select(DailyBarSnapshot)
                .where(
                    DailyBarSnapshot.symbol == symbol,
                    DailyBarSnapshot.trade_date >= start_date_iso,
                    DailyBarSnapshot.trade_date <= latest_trade_date,
                )
                .order_by(DailyBarSnapshot.trade_date.asc())
            )
            .scalars()
            .all()
        )
        return [
            DailyBarRow(
                trade_date=row.trade_date,
                open_price=row.open_price,
                close_price=row.close_price,
                high_price=row.high_price,
                low_price=row.low_price,
                volume=row.volume,
                amount=row.amount,
                pct_chg=row.pct_chg,
            )
            for row in rows
        ]

    def fetch_rows_for_symbols(
        self,
        symbols: list[str],
        start_date_iso: str,
        latest_trade_date: str,
    ) -> dict[str, list[DailyBarRow]]:
        if not symbols:
            return {}
        rows = (
            self.db.execute(
                select(DailyBarSnapshot)
                .where(
                    DailyBarSnapshot.symbol.in_(symbols),
                    DailyBarSnapshot.trade_date >= start_date_iso,
                    DailyBarSnapshot.trade_date <= latest_trade_date,
                )
                .order_by(DailyBarSnapshot.symbol.asc(), DailyBarSnapshot.trade_date.asc())
            )
            .scalars()
            .all()
        )
        grouped: dict[str, list[DailyBarRow]] = {}
        for row in rows:
            grouped.setdefault(row.symbol, []).append(
                DailyBarRow(
                    trade_date=row.trade_date,
                    open_price=row.open_price,
                    close_price=row.close_price,
                    high_price=row.high_price,
                    low_price=row.low_price,
                    volume=row.volume,
                    amount=row.amount,
                    pct_chg=row.pct_chg,
                )
            )
        return grouped

    def latest_timestamp_for_period(self, symbol: str, bar_period: str):
        return (
            self.db.execute(
                select(func.max(DailyBarSnapshot.trade_date)).where(DailyBarSnapshot.symbol == symbol)
            )
            .scalars()
            .first()
        )

    def upsert_rows(self, symbol: str, payloads: list[DailyBarRow]) -> None:
        if not payloads:
            return
        trade_dates = [item.trade_date for item in payloads]
        existing_rows = (
            self.db.execute(
                select(DailyBarSnapshot)
                .where(
                    DailyBarSnapshot.symbol == symbol,
                    DailyBarSnapshot.trade_date >= min(trade_dates),
                    DailyBarSnapshot.trade_date <= max(trade_dates),
                )
            )
            .scalars()
            .all()
        )
        rows_by_trade_date = {row.trade_date: row for row in existing_rows}
        new_rows: list[DailyBarSnapshot] = []
        update_rows: list[dict[str, object]] = []
        for item in payloads:
            row = rows_by_trade_date.get(item.trade_date)
            if row is None:
                new_rows.append(
                    DailyBarSnapshot(
                        symbol=symbol,
                        trade_date=item.trade_date,
                        open_price=item.open_price,
                        close_price=item.close_price,
                        high_price=item.high_price,
                        low_price=item.low_price,
                        volume=item.volume,
                        amount=item.amount,
                        pct_chg=item.pct_chg,
                    )
                )
                continue
            update_rows.append(
                {
                    "id": row.id,
                    "open_price": item.open_price,
                    "close_price": item.close_price,
                    "high_price": item.high_price,
                    "low_price": item.low_price,
                    "volume": item.volume,
                    "amount": item.amount,
                    "pct_chg": item.pct_chg,
                }
            )
        if new_rows:
            self.db.bulk_save_objects(new_rows)
        if update_rows:
            self.db.bulk_update_mappings(DailyBarSnapshot, update_rows)
