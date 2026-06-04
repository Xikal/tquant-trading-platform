from __future__ import annotations

from typing import Any

from sqlalchemy import and_
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import DailyBarSnapshot, Instrument
from app.repositories.low_buy.daily_history import DailyBarRow, DailyHistoryRepository
from app.services.daily_bar_refresh_checkpoint import DailyBarRefreshCheckpoint, DailyBarRefreshCheckpointStore
from app.services.latest_data_status import (
    MIN_STOCK_DAILY_BARS,
    daily_bar_freshness_status,
    expected_low_buy_trade_date,
)
from app.services.market_data import MarketDataService

DEFAULT_CHUNK_SIZE = 300


class DailyBarRefreshService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.market = MarketDataService()

    def refresh_latest(
        self,
        *,
        limit: int = 6000,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        expected_trade_date: str | None = None,
    ) -> dict[str, Any]:
        trade_date = expected_trade_date or expected_low_buy_trade_date(self.db)
        actual_chunk_size = max(1, chunk_size)
        symbols = self._stock_symbols(limit=limit)
        if not trade_date or not symbols:
            return {"ok": False, "trade_date": trade_date, "updated": 0, "message": "无可刷新标的"}
        chunks = list(_chunks(symbols, actual_chunk_size))
        checkpoint_store = DailyBarRefreshCheckpointStore(self.db)
        checkpoint = checkpoint_store.load(
            trade_date=trade_date,
            limit=len(symbols),
            chunk_size=actual_chunk_size,
            total_chunks=len(chunks),
        )
        if checkpoint and checkpoint.completed:
            completed = _completed_payload(self.db, checkpoint, requested=len(symbols), resumed=False)
            if completed.get("ok"):
                return completed
            checkpoint = None
        start_chunk_index = checkpoint.next_chunk_index if checkpoint else 0
        repository = DailyHistoryRepository(self.db)
        updated = checkpoint.updated if checkpoint else 0
        skipped = checkpoint.skipped if checkpoint else 0
        for chunk_index, chunk in enumerate(chunks[start_chunk_index:], start=start_chunk_index):
            quotes = self.market.get_quotes_batch(chunk, force_refresh=True, allow_slow_fallback=False)
            for symbol, quote in quotes.items():
                row = _row_from_quote(trade_date, quote)
                if row is None:
                    skipped += 1
                    continue
                repository.upsert_rows(symbol=symbol, payloads=[row])
                updated += 1
            self.db.flush()
            checkpoint_store.save(
                DailyBarRefreshCheckpoint(
                    trade_date=trade_date,
                    limit=len(symbols),
                    chunk_size=actual_chunk_size,
                    total_chunks=len(chunks),
                    last_chunk_index=chunk_index,
                    updated=updated,
                    skipped=skipped,
                    status="running",
                )
            )
            self.db.flush()
        final_checkpoint = DailyBarRefreshCheckpoint(
            trade_date=trade_date,
            limit=len(symbols),
            chunk_size=actual_chunk_size,
            total_chunks=len(chunks),
            last_chunk_index=len(chunks) - 1,
            updated=updated,
            skipped=skipped,
            status="completed",
        )
        checkpoint_store.save(final_checkpoint)
        self.db.flush()
        return _completed_payload(self.db, final_checkpoint, requested=len(symbols), resumed=start_chunk_index > 0)

    def _stock_symbols(self, *, limit: int) -> list[str]:
        rows = self.db.execute(
            select(Instrument.symbol)
            .outerjoin(
                DailyBarSnapshot,
                and_(DailyBarSnapshot.symbol == Instrument.symbol, DailyBarSnapshot.trade_date == _latest_daily_trade_date(self.db)),
            )
            .where(Instrument.instrument_type == "stock")
            .order_by(DailyBarSnapshot.amount.is_(None).asc(), DailyBarSnapshot.amount.desc(), Instrument.symbol.asc())
            .limit(max(1, limit))
        ).scalars().all()
        return [str(item) for item in rows if item]


def _row_from_quote(trade_date: str, quote) -> DailyBarRow | None:  # noqa: ANN001
    close_price = float(getattr(quote, "last_price", 0.0) or 0.0)
    open_price = float(getattr(quote, "open_price", 0.0) or close_price)
    high_price = float(getattr(quote, "high_price", 0.0) or close_price)
    low_price = float(getattr(quote, "low_price", 0.0) or close_price)
    change_pct = float(getattr(quote, "change_pct", 0.0) or 0.0)
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
        pct_chg=change_pct,
        pre_close=_resolve_pre_close(quote, close_price=close_price, change_pct=change_pct),
    )


def _chunks(items: list[str], size: int):
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _latest_daily_trade_date(db: Session):
    return select(DailyBarSnapshot.trade_date).order_by(DailyBarSnapshot.trade_date.desc()).limit(1).scalar_subquery()


def _completed_payload(
    db: Session,
    checkpoint: DailyBarRefreshCheckpoint,
    *,
    requested: int,
    resumed: bool,
) -> dict[str, Any]:
    freshness = daily_bar_freshness_status(db, checkpoint.trade_date)
    daily_bar_count = int(freshness.get("daily_bar_count") or 0)
    post_close_count = int(freshness.get("post_close_daily_bar_count") or 0)
    sufficient = daily_bar_count >= MIN_STOCK_DAILY_BARS and post_close_count >= MIN_STOCK_DAILY_BARS
    return {
        "ok": checkpoint.updated > 0 and sufficient,
        "status": "completed" if sufficient else str(freshness.get("daily_bar_freshness_status") or "insufficient_daily_bars"),
        "trade_date": checkpoint.trade_date,
        "updated": checkpoint.updated,
        "skipped": checkpoint.skipped,
        "requested": requested,
        "resumed": resumed,
        "checkpoint_status": checkpoint.status,
        "last_chunk_index": checkpoint.last_chunk_index,
        "total_chunks": checkpoint.total_chunks,
        "daily_bar_count": daily_bar_count,
        "min_daily_bar_count": MIN_STOCK_DAILY_BARS,
        "post_close_daily_bar_count": post_close_count,
        "post_close_fetch_cutoff": freshness.get("post_close_fetch_cutoff"),
        "latest_daily_bar_fetch_time": freshness.get("latest_daily_bar_fetch_time"),
        "post_close_daily_bars_ready": freshness.get("post_close_daily_bars_ready"),
    }


def _resolve_pre_close(quote, *, close_price: float, change_pct: float) -> float:  # noqa: ANN001
    explicit = float(getattr(quote, "prev_close", 0.0) or 0.0)
    if explicit > 0:
        return explicit
    denominator = 1 + change_pct / 100
    return round(close_price / denominator, 4) if denominator > 0 else close_price
