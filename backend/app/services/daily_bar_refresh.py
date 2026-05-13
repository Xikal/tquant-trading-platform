from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Instrument
from app.repositories.low_buy.daily_history import DailyBarRow, DailyHistoryRepository
from app.services.latest_data_status import expected_low_buy_trade_date
from app.services.market_data import MarketDataService

DEFAULT_CHUNK_SIZE = 300


class DailyBarRefreshService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.market = MarketDataService()

    def refresh_latest(self, *, limit: int = 6000, chunk_size: int = DEFAULT_CHUNK_SIZE) -> dict[str, Any]:
        trade_date = expected_low_buy_trade_date(self.db)
        symbols = self._stock_symbols(limit=limit)
        if not trade_date or not symbols:
            return {"ok": False, "trade_date": trade_date, "updated": 0, "message": "无可刷新标的"}
        repository = DailyHistoryRepository(self.db)
        updated = 0
        skipped = 0
        for chunk in _chunks(symbols, max(1, chunk_size)):
            quotes = self.market.get_quotes_batch(chunk, force_refresh=True, allow_slow_fallback=False)
            for symbol, quote in quotes.items():
                row = _row_from_quote(trade_date, quote)
                if row is None:
                    skipped += 1
                    continue
                repository.upsert_rows(symbol=symbol, payloads=[row])
                updated += 1
            self.db.flush()
        return {
            "ok": updated > 0,
            "trade_date": trade_date,
            "updated": updated,
            "skipped": skipped,
            "requested": len(symbols),
        }

    def _stock_symbols(self, *, limit: int) -> list[str]:
        rows = self.db.execute(
            select(Instrument.symbol)
            .where(Instrument.instrument_type == "stock")
            .order_by(Instrument.symbol.asc())
            .limit(max(1, limit))
        ).scalars().all()
        return [str(item) for item in rows if item]


def _row_from_quote(trade_date: str, quote) -> DailyBarRow | None:  # noqa: ANN001
    close_price = float(getattr(quote, "last_price", 0.0) or 0.0)
    open_price = float(getattr(quote, "open_price", 0.0) or close_price)
    high_price = float(getattr(quote, "high_price", 0.0) or close_price)
    low_price = float(getattr(quote, "low_price", 0.0) or close_price)
    if min(close_price, open_price, high_price, low_price) <= 0:
        return None
    return DailyBarRow(
        trade_date=trade_date,
        open_price=open_price,
        close_price=close_price,
        high_price=max(high_price, close_price, open_price),
        low_price=min(low_price, close_price, open_price),
        volume=float(getattr(quote, "volume", 0.0) or 0.0),
        amount=float(getattr(quote, "amount", 0.0) or 0.0),
        pct_chg=float(getattr(quote, "change_pct", 0.0) or 0.0),
    )


def _chunks(items: list[str], size: int):
    for index in range(0, len(items), size):
        yield items[index : index + size]
