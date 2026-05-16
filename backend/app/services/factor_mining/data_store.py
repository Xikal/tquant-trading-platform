from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import DailyBarSnapshot


class FactorDataStore:
    """Point-in-time daily bar reader for factor evaluation."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def daily_bars(self, *, start_date: str, end_date: str, limit_symbols: int) -> pd.DataFrame:
        start_date, end_date = self._resolve_window(start_date, end_date)
        symbols = self._liquid_symbols(start_date=start_date, end_date=end_date, limit=limit_symbols)
        if not symbols:
            return pd.DataFrame()
        rows = self.db.execute(
            select(DailyBarSnapshot)
            .where(DailyBarSnapshot.symbol.in_(symbols))
            .where(DailyBarSnapshot.trade_date >= start_date)
            .where(DailyBarSnapshot.trade_date <= end_date)
            .order_by(DailyBarSnapshot.symbol.asc(), DailyBarSnapshot.trade_date.asc())
        ).scalars().all()
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

    def _liquid_symbols(self, *, start_date: str, end_date: str, limit: int) -> list[str]:
        rows = self.db.execute(
            select(DailyBarSnapshot.symbol, func.sum(DailyBarSnapshot.amount).label("amount_sum"))
            .where(DailyBarSnapshot.trade_date >= start_date)
            .where(DailyBarSnapshot.trade_date <= end_date)
            .group_by(DailyBarSnapshot.symbol)
            .order_by(func.sum(DailyBarSnapshot.amount).desc())
            .limit(limit)
        ).all()
        return [str(row[0]) for row in rows]
