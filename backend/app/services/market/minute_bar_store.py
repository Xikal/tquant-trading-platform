from __future__ import annotations

import hashlib
import json
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

    def persist(
        self,
        quote: QuoteSnapshot,
        bars: Iterable[KlineBar],
        *,
        bar_period: str = "1m",
        skip_older_than_latest: bool = True,
    ) -> int:
        candidate_bars = list(bars)
        if not candidate_bars:
            return 0
        if skip_older_than_latest:
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
            row.bid_ask_spread = float(bar.bid_ask_spread or 0.0)
            row.premium_discount_pct = bar.premium_discount_pct
            row.tracking_index_symbol = bar.tracking_index_symbol or ""
            row.liquidity_tier = bar.liquidity_tier or "unknown"
            row.source = quote.data_source or "unknown"
            row.fetch_time = datetime.utcnow().isoformat(timespec="seconds")
            row.data_quality = quote.data_quality or quote.source_quality or "unknown"
            row.checksum = minute_bar_checksum(quote.symbol, bar, source=row.source, data_quality=row.data_quality)
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

    def list_bars_for_range(
        self,
        *,
        symbol: str,
        start: date,
        end: date,
        bar_period: str = "1m",
    ) -> list[MinuteBarSnapshot]:
        return list(
            self.db.execute(
                select(MinuteBarSnapshot)
                .where(
                    MinuteBarSnapshot.symbol == symbol,
                    MinuteBarSnapshot.trade_date >= start,
                    MinuteBarSnapshot.trade_date <= end,
                    MinuteBarSnapshot.bar_period == bar_period,
                )
                .order_by(MinuteBarSnapshot.trade_date.asc(), MinuteBarSnapshot.bar_timestamp.asc())
            )
            .scalars()
            .all()
        )

    def coverage_summary(
        self,
        *,
        symbols: list[str],
        start: date,
        end: date,
        bar_period: str = "1m",
    ) -> dict[str, object]:
        clean_symbols = sorted({str(symbol) for symbol in symbols if str(symbol or "").strip()})
        if not clean_symbols:
            return {
                "symbol_count": 0,
                "covered_symbol_count": 0,
                "coverage_pct": 0.0,
                "rows": 0,
                "bar_period": bar_period,
                "missing_symbols": [],
            }
        rows = self.db.execute(
            select(
                MinuteBarSnapshot.symbol,
                func.count(MinuteBarSnapshot.id),
                func.count(func.distinct(MinuteBarSnapshot.trade_date)),
                func.min(MinuteBarSnapshot.trade_date),
                func.max(MinuteBarSnapshot.trade_date),
            )
            .where(
                MinuteBarSnapshot.symbol.in_(clean_symbols),
                MinuteBarSnapshot.trade_date >= start,
                MinuteBarSnapshot.trade_date <= end,
                MinuteBarSnapshot.bar_period == bar_period,
            )
            .group_by(MinuteBarSnapshot.symbol)
        ).all()
        by_symbol = {
            str(symbol): {
                "rows": int(row_count or 0),
                "trade_days": int(day_count or 0),
                "start": str(min_date or ""),
                "end": str(max_date or ""),
            }
            for symbol, row_count, day_count, min_date, max_date in rows
        }
        covered = [symbol for symbol, item in by_symbol.items() if int(item["rows"] or 0) > 0]
        missing = [symbol for symbol in clean_symbols if symbol not in by_symbol]
        return {
            "symbol_count": len(clean_symbols),
            "covered_symbol_count": len(covered),
            "coverage_pct": round(len(covered) / max(len(clean_symbols), 1) * 100.0, 4),
            "rows": sum(int(item["rows"] or 0) for item in by_symbol.values()),
            "bar_period": bar_period,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "by_symbol": by_symbol,
            "missing_symbols": missing[:100],
        }


def minute_bar_checksum(symbol: str, bar: KlineBar, *, source: str, data_quality: str) -> str:
    payload = {
        "symbol": symbol,
        "timestamp": bar.timestamp,
        "open": round(float(bar.open or 0.0), 6),
        "close": round(float(bar.close or 0.0), 6),
        "high": round(float(bar.high or 0.0), 6),
        "low": round(float(bar.low or 0.0), 6),
        "volume": round(float(bar.volume or 0.0), 3),
        "amount": round(float(bar.amount or 0.0), 3),
        "bid_ask_spread": round(float(bar.bid_ask_spread or 0.0), 6),
        "premium_discount_pct": None if bar.premium_discount_pct is None else round(float(bar.premium_discount_pct), 6),
        "tracking_index_symbol": bar.tracking_index_symbol or "",
        "liquidity_tier": bar.liquidity_tier or "unknown",
        "source": source,
        "data_quality": data_quality,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
