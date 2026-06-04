from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import DailyBarSnapshot


FORWARD_PATH_FIELDS = (
    "return_1d",
    "return_2d",
    "return_3d",
    "return_4d",
    "return_5d",
    "max_gain_5d",
    "max_drawdown_5d",
)


@dataclass(frozen=True)
class ForwardPathResult:
    status: str
    values: dict[str, float]
    missing_days: int = 0


def enrich_trade_forward_path(db: Session, trade: Any) -> ForwardPathResult:
    if all(getattr(trade, field, None) is not None for field in FORWARD_PATH_FIELDS):
        return ForwardPathResult(
            status="ok",
            values={field: _float_attr(trade, field) for field in FORWARD_PATH_FIELDS},
        )
    symbol = str(getattr(trade, "symbol", "") or "").strip()
    entry_date = str(getattr(trade, "entry_date", "") or "").strip()
    entry_price = float(getattr(trade, "entry_price", 0.0) or 0.0)
    if not symbol or not entry_date or entry_price <= 0:
        return ForwardPathResult(status="no_daily_return_path", values={})

    bars = _forward_bars(db, symbol=symbol, entry_date=entry_date, limit=5)
    if not bars:
        return ForwardPathResult(status="no_daily_return_path", values={})
    if any(bool(getattr(row, "is_suspended", False) or getattr(row, "is_delisted", False)) for row in bars):
        return ForwardPathResult(status="suspended", values={})
    valid_bars = [row for row in bars if _valid_bar(row)]
    if len(valid_bars) < len(bars):
        return ForwardPathResult(status="partial_path", values={}, missing_days=5 - len(valid_bars))
    if len(valid_bars) < 5:
        return ForwardPathResult(status="partial_path", values={}, missing_days=5 - len(valid_bars))

    close_returns = [
        _return_pct(float(row.close_price or 0.0), entry_price)
        for row in valid_bars[:5]
    ]
    high_returns = [
        _return_pct(float(row.high_price or 0.0), entry_price)
        for row in valid_bars[:5]
    ]
    low_returns = [
        _return_pct(float(row.low_price or 0.0), entry_price)
        for row in valid_bars[:5]
    ]
    values = {
        f"return_{index}d": close_returns[index - 1]
        for index in range(1, 6)
    }
    values["max_gain_5d"] = max(high_returns)
    values["max_drawdown_5d"] = min(low_returns)
    return ForwardPathResult(status="ok", values=values)


def _forward_bars(db: Session, *, symbol: str, entry_date: str, limit: int) -> list[DailyBarSnapshot]:
    return list(
        db.execute(
            select(DailyBarSnapshot)
            .where(
                DailyBarSnapshot.symbol == symbol,
                DailyBarSnapshot.trade_date > entry_date,
            )
            .order_by(DailyBarSnapshot.trade_date.asc())
            .limit(limit)
        ).scalars().all()
    )


def _valid_bar(row: DailyBarSnapshot) -> bool:
    open_price = float(row.open_price or 0.0)
    close_price = float(row.close_price or 0.0)
    high_price = float(row.high_price or 0.0)
    low_price = float(row.low_price or 0.0)
    if min(open_price, close_price, high_price, low_price) <= 0:
        return False
    return high_price >= max(open_price, close_price, low_price)


def _return_pct(price: float, entry_price: float) -> float:
    return (float(price) / float(entry_price) - 1.0) * 100.0


def _float_attr(item: Any, field: str) -> float:
    return float(getattr(item, field, 0.0) or 0.0)
