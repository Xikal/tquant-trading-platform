from __future__ import annotations

from datetime import date, datetime
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import MinuteBarSnapshot
from app.models.schemas import KlineBar, QuoteSnapshot


def parse_minute_trade_date(timestamp: str) -> date | None:
    text = str(timestamp or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y%m%d%H%M"):
        try:
            return datetime.strptime(text[: len(datetime.now().strftime(fmt))], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


class MinuteBarSnapshotStore:
    """Persistence seam for minute bars so query shape can evolve independently."""

    def __init__(self, db: Session):
        self.db = db

    def persist(self, quote: QuoteSnapshot, bars: Iterable[KlineBar], *, bar_period: str = "1m") -> int:
        candidate_bars = list(bars)
        if not candidate_bars:
            return 0
        latest_stored = self.db.execute(
            select(func.max(MinuteBarSnapshot.bar_timestamp)).where(
                MinuteBarSnapshot.symbol == quote.symbol,
                MinuteBarSnapshot.bar_period == bar_period,
            )
        ).scalar_one()
        candidate_bars = [bar for bar in candidate_bars if not latest_stored or bar.timestamp >= str(latest_stored)]
        if not candidate_bars:
            return 0
        existing_rows = self.db.execute(
            select(MinuteBarSnapshot).where(
                MinuteBarSnapshot.symbol == quote.symbol,
                MinuteBarSnapshot.bar_period == bar_period,
                MinuteBarSnapshot.bar_timestamp.in_([bar.timestamp for bar in candidate_bars]),
            )
        ).scalars().all()
        rows_by_timestamp = {row.bar_timestamp: row for row in existing_rows}
        persisted = 0
        for bar in candidate_bars:
            row = rows_by_timestamp.get(bar.timestamp)
            if row is None:
                row = MinuteBarSnapshot(
                    symbol=quote.symbol,
                    market=quote.market,
                    instrument_type=quote.instrument_type,
                    bar_period=bar_period,
                    bar_timestamp=bar.timestamp,
                )
                self.db.add(row)
                persisted += 1
            row.trade_date = parse_minute_trade_date(bar.timestamp)
            row.quote_timestamp = quote.timestamp
            row.last_price = quote.last_price
            row.change_pct = quote.change_pct
            row.open_price = bar.open
            row.close_price = bar.close
            row.high_price = bar.high
            row.low_price = bar.low
            row.volume = bar.volume
            row.amount = bar.amount
        if persisted or existing_rows:
            self.db.commit()
        return len(candidate_bars)

    def list_bars(
        self,
        *,
        symbol: str,
        trade_date: date,
        bar_period: str = "1m",
        limit: int = 240,
    ) -> list[MinuteBarSnapshot]:
        return list(
            self.db.execute(
                select(MinuteBarSnapshot)
                .where(
                    MinuteBarSnapshot.symbol == symbol,
                    MinuteBarSnapshot.trade_date == trade_date,
                    MinuteBarSnapshot.bar_period == bar_period,
                )
                .order_by(MinuteBarSnapshot.bar_timestamp.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
