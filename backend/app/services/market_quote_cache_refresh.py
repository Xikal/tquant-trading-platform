from __future__ import annotations

from datetime import datetime, time as dt_time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_now
from app.models.entities import DailyBarSnapshot, Instrument, UserWatchlist
from app.models.schemas import QuoteSnapshot
from app.services.market.local_quote_cache import write_local_quote_snapshots
from app.services.market_data import MarketDataService

DEFAULT_LIMIT = 200


class MarketQuoteCacheRefreshService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.market = MarketDataService()

    def refresh(self, *, limit: int = DEFAULT_LIMIT) -> dict[str, object]:
        symbols = self._target_symbols(limit=limit)
        if not symbols:
            return {"ok": True, "count": 0, "symbols": [], "message": "无可预热行情标的"}
        quotes = self.market.get_quotes_batch(symbols, force_refresh=True, allow_slow_fallback=True)
        if len(quotes) < len(symbols):
            quotes.update({symbol: quote for symbol, quote in self._daily_fallback_quotes(symbols).items() if symbol not in quotes})
        redis_written = write_local_quote_snapshots(quotes)
        return {
            "ok": True,
            "count": len(quotes),
            "redis_written": redis_written,
            "missing_count": max(len(symbols) - len(quotes), 0),
            "symbols": symbols[:20],
            "message": f"已刷新 {len(quotes)} 只标的本地行情缓存，Redis 写入 {redis_written} 条",
        }

    def _daily_fallback_quotes(self, symbols: list[str]) -> dict[str, QuoteSnapshot]:
        cleaned = list(dict.fromkeys(symbol for symbol in symbols if symbol))
        if not cleaned:
            return {}
        latest_date = self.db.execute(select(DailyBarSnapshot.trade_date).order_by(DailyBarSnapshot.trade_date.desc()).limit(1)).scalar()
        if not latest_date:
            return {}
        rows = self.db.execute(
            select(DailyBarSnapshot, Instrument.name)
            .outerjoin(Instrument, Instrument.symbol == DailyBarSnapshot.symbol)
            .where(DailyBarSnapshot.trade_date == latest_date)
            .where(DailyBarSnapshot.symbol.in_(cleaned))
        ).all()
        result: dict[str, QuoteSnapshot] = {}
        for row, name in rows:
            if not row.symbol or float(row.close_price or 0.0) <= 0:
                continue
            prev_close = float(row.pre_close or 0.0)
            close_price = float(row.close_price or 0.0)
            result[row.symbol] = QuoteSnapshot(
                symbol=row.symbol,
                name=str(name or row.symbol),
                market=str(row.market or "CN"),
                instrument_type=str(row.instrument_type or "stock"),
                last_price=close_price,
                change_pct=float(row.pct_chg or 0.0),
                change_amount=round(close_price - prev_close, 4) if prev_close else 0.0,
                open_price=float(row.open_price or 0.0),
                high_price=float(row.high_price or 0.0),
                low_price=float(row.low_price or 0.0),
                prev_close=prev_close,
                volume=float(row.volume or 0.0),
                amount=float(row.amount or 0.0),
                timestamp=str(row.trade_date),
                data_source="mysql_daily_bar_snapshot",
                source_quality="stale",
                data_quality="stale",
                data_quality_message="实时行情未命中，使用 MySQL 最新日线快照兜底。",
                is_stale=True,
            )
        return result

    def _target_symbols(self, *, limit: int) -> list[str]:
        symbols: list[str] = []
        symbols.extend(self._watchlist_symbols(limit=max(20, min(limit, 80))))
        symbols.extend(self._top_liquidity_symbols(limit=max(50, limit)))
        seen: set[str] = set()
        ordered: list[str] = []
        for symbol in symbols:
            clean = str(symbol or "").strip()
            if len(clean) != 6 or clean in seen:
                continue
            seen.add(clean)
            ordered.append(clean)
            if len(ordered) >= limit:
                break
        return ordered

    def _watchlist_symbols(self, *, limit: int) -> list[str]:
        rows = self.db.execute(
            select(UserWatchlist.symbol).order_by(UserWatchlist.updated_at.desc()).limit(limit)
        ).scalars().all()
        return [str(item) for item in rows if item]

    def _top_liquidity_symbols(self, *, limit: int) -> list[str]:
        latest_date = self.db.execute(select(DailyBarSnapshot.trade_date).order_by(DailyBarSnapshot.trade_date.desc()).limit(1)).scalar()
        if not latest_date:
            return []
        rows = self.db.execute(
            select(DailyBarSnapshot.symbol)
            .join(Instrument, Instrument.symbol == DailyBarSnapshot.symbol)
            .where(DailyBarSnapshot.trade_date == latest_date)
            .where(~Instrument.name.like("ST%"))
            .where(~Instrument.name.like("*ST%"))
            .where(~DailyBarSnapshot.symbol.like("30%"))
            .where(~DailyBarSnapshot.symbol.like("68%"))
            .order_by(DailyBarSnapshot.amount.desc())
            .limit(limit)
        ).scalars().all()
        return [str(item) for item in rows if item]


def quote_cache_refresh_due(now: datetime | None = None) -> bool:
    current = now or beijing_now()
    if current.weekday() >= 5:
        return False
    current_time = current.time()
    morning = dt_time(9, 25) <= current_time <= dt_time(11, 31)
    afternoon = dt_time(12, 55) <= current_time <= dt_time(15, 5)
    return morning or afternoon


def quote_cache_refresh_bucket(now: datetime | None = None) -> str:
    current = now or beijing_now()
    bucket_minute = (current.minute // 1)
    return current.strftime(f"%Y%m%d%H{bucket_minute:02d}")
