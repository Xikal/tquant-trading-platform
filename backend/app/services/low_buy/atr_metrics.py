from __future__ import annotations

from typing import Any

ATR_WINDOW = 14
ATR_SOURCE = "daily_ohlcv_true_range_14"


def compute_daily_atr(history: Any, period: int = ATR_WINDOW) -> float:
    """Compute daily ATR from OHLCV history with a simple TR average.

    The function intentionally accepts a DataFrame-like object to avoid tying
    strategy modules to pandas at import time.
    """

    if history is None or getattr(history, "empty", True):
        return 0.0
    if not all(column in history.columns for column in ("high", "low", "close")):
        return 0.0
    rows = history.tail(max(int(period) + 1, 2))
    if len(rows) < 2:
        return 0.0
    highs = [float(value) for value in rows["high"].tolist()]
    lows = [float(value) for value in rows["low"].tolist()]
    closes = [float(value) for value in rows["close"].tolist()]
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
    if not true_ranges:
        return 0.0
    selected = true_ranges[-max(int(period), 1) :]
    return round(sum(selected) / len(selected), 4)
