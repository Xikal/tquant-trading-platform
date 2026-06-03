from __future__ import annotations

from typing import Any

from app.services.finance.rust_math import atr as rust_math_atr
from app.services.read_models.indicator_cache import get_or_compute_indicator, hash_indicator_params

ATR_WINDOW = 14
ATR_SOURCE = "daily_ohlcv_wilder_true_range_14"


def compute_daily_atr(history: Any, period: int = ATR_WINDOW) -> float:
    """Compute daily ATR from OHLCV history using Wilder RMA.

    The function intentionally accepts a DataFrame-like object to avoid tying
    strategy modules to pandas at import time.
    """

    period = max(int(period or ATR_WINDOW), 1)
    if history is None or getattr(history, "empty", True):
        return 0.0
    if not all(column in history.columns for column in ("high", "low", "close")):
        return 0.0
    rows = history.tail(max(period * 2, 2))
    if len(rows) < period * 2:
        return 0.0
    highs = [float(value) for value in rows["high"].tolist()]
    lows = [float(value) for value in rows["low"].tolist()]
    closes = [float(value) for value in rows["close"].tolist()]
    rust_values = rust_math_atr(highs, lows, closes, period)
    if rust_values:
        latest = rust_values[-1]
        if latest is not None:
            return round(float(latest), 4)
    true_ranges: list[float] = []
    for index in range(1, len(rows)):
        previous_close = closes[index - 1]
        true_ranges.append(
            max(
                highs[index] - lows[index],
                abs(highs[index] - previous_close),
                abs(lows[index] - previous_close),
            )
        )
    if len(true_ranges) < period:
        return 0.0
    atr_value = sum(true_ranges[:period]) / period
    for value in true_ranges[period:]:
        atr_value = ((atr_value * (period - 1)) + value) / period
    return round(atr_value, 4)


def compute_daily_atr_cached(
    history: Any,
    *,
    symbol: str,
    trade_date: str,
    period: int = ATR_WINDOW,
    indicator_version: str = ATR_SOURCE,
) -> float:
    if history is None or getattr(history, "empty", True):
        return 0.0
    tail = history.tail(max(int(period or ATR_WINDOW) * 2, 2))
    params_hash = hash_indicator_params(
        {
            "period": int(period or ATR_WINDOW),
            "high": _column_values(tail, "high"),
            "low": _column_values(tail, "low"),
            "close": _column_values(tail, "close"),
        }
    )
    return float(
        get_or_compute_indicator(
            indicator="atr",
            symbol=symbol,
            trade_date=trade_date,
            params_hash=params_hash,
            indicator_version=indicator_version,
            loader=lambda: compute_daily_atr(history, period),
        )
    )


def _column_values(history: Any, column: str) -> list[float]:
    if history is None or getattr(history, "empty", True) or column not in history.columns:
        return []
    return [float(value) for value in history[column].tolist()]
