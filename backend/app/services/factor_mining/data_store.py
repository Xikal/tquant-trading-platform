from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import DailyBarSnapshot


class FactorDataStore:
    """Point-in-time daily bar reader for factor evaluation."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def daily_bars(
        self,
        *,
        start_date: str,
        end_date: str,
        limit_symbols: int,
        as_of_date: str | None = None,
    ) -> pd.DataFrame:
        start_date, end_date = self._resolve_window(start_date, end_date)
        as_of = _as_of_end(as_of_date)
        symbols = self._liquid_symbols(start_date=start_date, end_date=end_date, limit=limit_symbols, as_of=as_of)
        if not symbols:
            return pd.DataFrame()
        statement = (
            select(DailyBarSnapshot)
            .where(DailyBarSnapshot.symbol.in_(symbols))
            .where(DailyBarSnapshot.trade_date >= start_date)
            .where(DailyBarSnapshot.trade_date <= end_date)
            .order_by(DailyBarSnapshot.symbol.asc(), DailyBarSnapshot.trade_date.asc())
        )
        if as_of is not None:
            statement = statement.where(DailyBarSnapshot.created_at <= as_of)
        rows = self.db.execute(statement).scalars().all()
        return pd.DataFrame(
            [
                {
                    "symbol": row.symbol,
                    "trade_date": row.trade_date,
                    "open_price": row.open_price,
                    "close_price": row.close_price,
                    "high_price": row.high_price,
                    "low_price": row.low_price,
                    "volume": row.volume,
                    "amount": row.amount,
                    "pct_chg": row.pct_chg,
                    "pre_close": row.pre_close,
                }
                for row in rows
            ]
        )

    def point_in_time_bars(self, *, as_of_date: str, lookback_days: int = 365 * 3, limit_symbols: int = 500) -> pd.DataFrame:
        try:
            end_day = date.fromisoformat(as_of_date)
            start_date = (end_day - timedelta(days=lookback_days)).isoformat()
        except ValueError:
            start_date = ""
        return self.daily_bars(
            start_date=start_date,
            end_date=as_of_date,
            limit_symbols=limit_symbols,
            as_of_date=as_of_date,
        )

    def _resolve_window(self, start_date: str, end_date: str) -> tuple[str, str]:
        latest = self.db.execute(select(func.max(DailyBarSnapshot.trade_date))).scalar()
        resolved_end = end_date or str(latest or "")
        if start_date:
            return start_date, resolved_end
        try:
            end_day = date.fromisoformat(resolved_end)
            return (end_day - timedelta(days=365 * 3)).isoformat(), resolved_end
        except ValueError:
            return "", resolved_end

    def _liquid_symbols(self, *, start_date: str, end_date: str, limit: int, as_of: datetime | None) -> list[str]:
        statement = (
            select(DailyBarSnapshot.symbol, func.sum(DailyBarSnapshot.amount).label("amount_sum"))
            .where(DailyBarSnapshot.trade_date >= start_date)
            .where(DailyBarSnapshot.trade_date <= end_date)
            .group_by(DailyBarSnapshot.symbol)
            .order_by(func.sum(DailyBarSnapshot.amount).desc())
            .limit(limit)
        )
        if as_of is not None:
            statement = statement.where(DailyBarSnapshot.created_at <= as_of)
        rows = self.db.execute(statement).all()
        return [str(row[0]) for row in rows]


def _as_of_end(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.combine(date.fromisoformat(value), time.max)
    except ValueError:
        return None
