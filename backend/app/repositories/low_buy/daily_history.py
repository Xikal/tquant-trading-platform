from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.timezone import beijing_now
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
    pre_close: float = 0.0
    limit_up_price: float = 0.0
    limit_down_price: float = 0.0
    is_suspended: bool = False
    is_st: bool = False
    is_delisted: bool = False
    source: str = "unknown"
    fetch_time: str = ""
    adjusted_mode: str = "unknown"
    checksum: str = ""
    data_quality: str = "unknown"


def _daily_bar_row_columns():
    return (
        DailyBarSnapshot.trade_date,
        DailyBarSnapshot.open_price,
        DailyBarSnapshot.close_price,
        DailyBarSnapshot.high_price,
        DailyBarSnapshot.low_price,
        DailyBarSnapshot.volume,
        DailyBarSnapshot.amount,
        DailyBarSnapshot.pct_chg,
        DailyBarSnapshot.pre_close,
        DailyBarSnapshot.limit_up_price,
        DailyBarSnapshot.limit_down_price,
        DailyBarSnapshot.is_suspended,
        DailyBarSnapshot.is_st,
        DailyBarSnapshot.is_delisted,
        DailyBarSnapshot.source,
        DailyBarSnapshot.fetch_time,
        DailyBarSnapshot.adjusted_mode,
        DailyBarSnapshot.checksum,
        DailyBarSnapshot.data_quality,
    )


def _daily_bar_row_query():
    return select(*_daily_bar_row_columns())


def _daily_bar_insert_payload(symbol: str, item: DailyBarRow) -> dict[str, object]:
    return {
        "symbol": symbol,
        "market": "CN",
        "instrument_type": "stock",
        "trade_date": _as_iso_date(item.trade_date),
        "open_price": item.open_price,
        "close_price": item.close_price,
        "high_price": item.high_price,
        "low_price": item.low_price,
        "volume": item.volume,
        "amount": item.amount,
        "pct_chg": item.pct_chg,
        "pre_close": item.pre_close,
        "limit_up_price": item.limit_up_price,
        "limit_down_price": item.limit_down_price,
        "is_suspended": item.is_suspended,
        "is_st": item.is_st,
        "is_delisted": item.is_delisted,
        "source": item.source,
        "fetch_time": item.fetch_time or _now_fetch_time(),
        "adjusted_mode": item.adjusted_mode,
        "checksum": item.checksum or daily_bar_checksum(symbol, item),
        "data_quality": item.data_quality,
    }


def _daily_bar_insert_statement():
    return text(
        """
        INSERT INTO daily_bar_snapshots (
            symbol, market, instrument_type, trade_date,
            open_price, close_price, high_price, low_price,
            volume, amount, pct_chg, pre_close,
            limit_up_price, limit_down_price, is_suspended, is_st, is_delisted
            , source, fetch_time, adjusted_mode, checksum, data_quality
        )
        VALUES (
            :symbol, :market, :instrument_type, :trade_date,
            :open_price, :close_price, :high_price, :low_price,
            :volume, :amount, :pct_chg, :pre_close,
            :limit_up_price, :limit_down_price, :is_suspended, :is_st, :is_delisted,
            :source, :fetch_time, :adjusted_mode, :checksum, :data_quality
        )
        """
    )


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
                _daily_bar_row_query()
                .where(
                    DailyBarSnapshot.symbol == symbol,
                    DailyBarSnapshot.trade_date >= start_date_iso,
                    DailyBarSnapshot.trade_date <= latest_trade_date,
                )
                .order_by(DailyBarSnapshot.trade_date.asc())
            )
            .all()
        )
        return [
            DailyBarRow(
                trade_date=_as_iso_date(row.trade_date),
                open_price=row.open_price,
                close_price=row.close_price,
                high_price=row.high_price,
                low_price=row.low_price,
                volume=row.volume,
                amount=row.amount,
                pct_chg=row.pct_chg,
                pre_close=row.pre_close,
                limit_up_price=row.limit_up_price,
                limit_down_price=row.limit_down_price,
                is_suspended=bool(row.is_suspended),
                is_st=bool(row.is_st),
                is_delisted=bool(row.is_delisted),
                source=row.source,
                fetch_time=row.fetch_time,
                adjusted_mode=row.adjusted_mode,
                checksum=row.checksum,
                data_quality=row.data_quality,
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
                select(DailyBarSnapshot.symbol, *_daily_bar_row_columns())
                .where(
                    DailyBarSnapshot.symbol.in_(symbols),
                    DailyBarSnapshot.trade_date >= start_date_iso,
                    DailyBarSnapshot.trade_date <= latest_trade_date,
                )
                .order_by(DailyBarSnapshot.symbol.asc(), DailyBarSnapshot.trade_date.asc())
            )
            .all()
        )
        grouped: dict[str, list[DailyBarRow]] = {}
        for row in rows:
            grouped.setdefault(row.symbol, []).append(
                DailyBarRow(
                    trade_date=_as_iso_date(row.trade_date),
                    open_price=row.open_price,
                    close_price=row.close_price,
                    high_price=row.high_price,
                    low_price=row.low_price,
                    volume=row.volume,
                    amount=row.amount,
                    pct_chg=row.pct_chg,
                    pre_close=row.pre_close,
                    limit_up_price=row.limit_up_price,
                    limit_down_price=row.limit_down_price,
                    is_suspended=bool(row.is_suspended),
                    is_st=bool(row.is_st),
                    is_delisted=bool(row.is_delisted),
                    source=row.source,
                    fetch_time=row.fetch_time,
                    adjusted_mode=row.adjusted_mode,
                    checksum=row.checksum,
                    data_quality=row.data_quality,
                )
            )
        return grouped

    def fetch_light_rows_for_symbols(
        self,
        symbols: list[str],
        start_date_iso: str,
        latest_trade_date: str,
    ) -> dict[str, list[DailyBarRow]]:
        if not symbols:
            return {}
        rows = (
            self.db.execute(
                select(
                    DailyBarSnapshot.symbol,
                    DailyBarSnapshot.trade_date,
                    DailyBarSnapshot.close_price,
                    DailyBarSnapshot.high_price,
                    DailyBarSnapshot.low_price,
                    DailyBarSnapshot.is_suspended,
                    DailyBarSnapshot.is_delisted,
                    DailyBarSnapshot.source,
                    DailyBarSnapshot.fetch_time,
                    DailyBarSnapshot.data_quality,
                )
                .where(
                    DailyBarSnapshot.symbol.in_(symbols),
                    DailyBarSnapshot.trade_date >= start_date_iso,
                    DailyBarSnapshot.trade_date <= latest_trade_date,
                )
                .order_by(DailyBarSnapshot.symbol.asc(), DailyBarSnapshot.trade_date.asc())
            )
            .all()
        )
        grouped: dict[str, list[DailyBarRow]] = {}
        for row in rows:
            close_price = float(row.close_price or 0.0)
            grouped.setdefault(row.symbol, []).append(
                DailyBarRow(
                    trade_date=_as_iso_date(row.trade_date),
                    open_price=close_price,
                    close_price=close_price,
                    high_price=float(row.high_price or close_price),
                    low_price=float(row.low_price or close_price),
                    volume=0.0,
                    amount=0.0,
                    pct_chg=0.0,
                    is_suspended=bool(row.is_suspended),
                    is_delisted=bool(row.is_delisted),
                    source=row.source,
                    fetch_time=row.fetch_time,
                    data_quality=row.data_quality,
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
        trade_dates = [_as_iso_date(item.trade_date) for item in payloads]
        existing_rows = (
            self.db.execute(
                select(DailyBarSnapshot.id, DailyBarSnapshot.trade_date)
                .where(
                    DailyBarSnapshot.symbol == symbol,
                    DailyBarSnapshot.trade_date >= min(trade_dates),
                    DailyBarSnapshot.trade_date <= max(trade_dates),
                )
            )
            .all()
        )
        ids_by_trade_date = {_as_iso_date(row.trade_date): row.id for row in existing_rows}
        new_rows: list[dict[str, object]] = []
        update_rows: list[dict[str, object]] = []
        for item in payloads:
            row_id = ids_by_trade_date.get(_as_iso_date(item.trade_date))
            if row_id is None:
                new_rows.append(_daily_bar_insert_payload(symbol, item))
                continue
            update_rows.append(
                {
                    "id": row_id,
                    "open_price": item.open_price,
                    "close_price": item.close_price,
                    "high_price": item.high_price,
                    "low_price": item.low_price,
                    "volume": item.volume,
                    "amount": item.amount,
                    "pct_chg": item.pct_chg,
                    "pre_close": item.pre_close,
                    "limit_up_price": item.limit_up_price,
                    "limit_down_price": item.limit_down_price,
                    "is_suspended": item.is_suspended,
                    "is_st": item.is_st,
                    "is_delisted": item.is_delisted,
                    "source": item.source,
                    "fetch_time": item.fetch_time or _now_fetch_time(),
                    "adjusted_mode": item.adjusted_mode,
                    "checksum": item.checksum or daily_bar_checksum(symbol, item),
                    "data_quality": item.data_quality,
                }
            )
        if new_rows:
            self.db.execute(_daily_bar_insert_statement(), new_rows)
        if update_rows:
            self.db.bulk_update_mappings(DailyBarSnapshot, update_rows)


def _as_iso_date(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def _now_fetch_time() -> str:
    return beijing_now().replace(tzinfo=None).isoformat(timespec="seconds")


def daily_bar_checksum(symbol: str, item: DailyBarRow) -> str:
    payload = {
        "symbol": symbol,
        "trade_date": _as_iso_date(item.trade_date),
        "open": round(float(item.open_price or 0.0), 6),
        "close": round(float(item.close_price or 0.0), 6),
        "high": round(float(item.high_price or 0.0), 6),
        "low": round(float(item.low_price or 0.0), 6),
        "volume": round(float(item.volume or 0.0), 3),
        "amount": round(float(item.amount or 0.0), 3),
        "pct_chg": round(float(item.pct_chg or 0.0), 6),
        "pre_close": round(float(item.pre_close or 0.0), 6),
        "limit_up_price": round(float(item.limit_up_price or 0.0), 6),
        "limit_down_price": round(float(item.limit_down_price or 0.0), 6),
        "is_suspended": bool(item.is_suspended),
        "is_st": bool(item.is_st),
        "is_delisted": bool(item.is_delisted),
        "adjusted_mode": item.adjusted_mode,
        "source": item.source,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
