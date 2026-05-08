from __future__ import annotations

from math import isfinite
from numbers import Real
from typing import Any

from app.models.schemas import KlineBar


def closes_from_bars(bars: list[KlineBar]) -> list[float]:
    return [bar.close for bar in bars]


def volumes_from_bars(bars: list[KlineBar]) -> list[float]:
    return [bar.volume for bar in bars]


def moving_average(values: list[float], window: int) -> float:
    if not values:
        return 0.0
    if len(values) < window:
        return round(sum(values) / len(values), 4)
    return round(sum(values[-window:]) / window, 4)


def exponential_moving_average(values: list[float], window: int) -> float:
    if not values:
        return 0.0
    if window <= 1:
        return round(values[-1], 4)
    if len(values) < window:
        return round(sum(values) / len(values), 4)
    multiplier = 2 / (window + 1)
    ema = sum(values[:window]) / window
    for value in values[window:]:
        ema = (value - ema) * multiplier + ema
    return round(ema, 4)


def macd(values: list[float]) -> tuple[float, float, float]:
    dif, dea, hist, _valid = macd_with_validity(values)
    return dif, dea, hist


def macd_with_validity(values: list[float]) -> tuple[float, float, float, bool]:
    if len(values) < 35:
        return (0.0, 0.0, 0.0, False)
    if any(not isinstance(value, Real) or not isfinite(float(value)) for value in values):
        return (0.0, 0.0, 0.0, False)
    sanitized = [float(value) for value in values]
    ema12_series = _ema_series(sanitized, 12)
    ema26_series = _ema_series(sanitized, 26)
    dif_series = [
        fast - slow
        for fast, slow in zip(ema12_series, ema26_series)
        if fast is not None and slow is not None
    ]
    if len(dif_series) < 9:
        return (0.0, 0.0, 0.0, False)
    dea = exponential_moving_average(dif_series, 9)
    dif = round(dif_series[-1], 4)
    hist = round((dif - dea) * 2, 4)
    return dif, dea, hist, True


def macd_or_none(values: list[float]) -> tuple[float, float, float] | None:
    dif, dea, hist, valid = macd_with_validity(values)
    if not valid:
        return None
    return dif, dea, hist


def _ema_series(values: list[float], window: int) -> list[float | None]:
    """Return EMA series using SMA as the initial seed.

    This matches the common technical-analysis convention used by most charting
    tools better than seeding from the first close.
    """

    result: list[float | None] = [None] * len(values)
    if not values or len(values) < window:
        return result
    multiplier = 2 / (window + 1)
    ema = sum(values[:window]) / window
    result[window - 1] = ema
    for index in range(window, len(values)):
        ema = (values[index] - ema) * multiplier + ema
        result[index] = ema
    return result


def rsi(values: list[float], period: int = 14) -> float:
    if len(values) < period + 1:
        return 50.0
    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(values[:period], values[1 : period + 1]):
        diff = current - previous
        gains.append(max(diff, 0.0))
        losses.append(abs(min(diff, 0.0)))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    for previous, current in zip(values[period:-1], values[period + 1 :]):
        diff = current - previous
        gain = max(diff, 0.0)
        loss = abs(min(diff, 0.0))
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 4)


def atr(bars: list[KlineBar], period: int = 14) -> float:
    if len(bars) < period + 1:
        return 0.0
    ranges: list[float] = []
    for previous, current in zip(bars[:period], bars[1 : period + 1]):
        tr = max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        )
        ranges.append(tr)
    atr_value = sum(ranges) / period
    for previous, current in zip(bars[period:-1], bars[period + 1 :]):
        tr = max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        )
        atr_value = ((atr_value * (period - 1)) + tr) / period
    return round(atr_value, 4)


def vwap(bars: list[KlineBar]) -> float:
    total_turnover = 0.0
    total_volume = 0.0
    for bar in bars:
        typical_price = (bar.high + bar.low + bar.close) / 3
        total_turnover += typical_price * max(bar.volume, 1)
        total_volume += max(bar.volume, 1)
    if total_volume == 0:
        return 0.0
    return round(total_turnover / total_volume, 4)


def volume_ratio(bars: list[KlineBar], lookback: int = 20) -> float:
    if not bars:
        return 0.0
    volumes = volumes_from_bars(bars)
    latest = volumes[-1]
    base = moving_average(volumes[:-1] or volumes, min(lookback, max(1, len(volumes[:-1]))))
    if base <= 0:
        return 1.0
    return round(latest / base, 4)


def intraday_amplitude(bars: list[KlineBar], prev_close: float | None = None) -> float:
    if not bars:
        return 0.0
    highest = max(bar.high for bar in bars)
    lowest = min(bar.low for bar in bars)
    baseline = float(prev_close or 0.0) or bars[0].open or bars[0].close
    if baseline == 0:
        return 0.0
    return round((highest - lowest) / baseline * 100, 4)


def trend_slope(values: list[float], window: int = 10) -> float:
    if len(values) < window + 1:
        return 0.0
    start = values[-window - 1]
    end = values[-1]
    if start == 0:
        return 0.0
    return round((end - start) / start * 100, 4)


def obv(bars: list[KlineBar]) -> float:
    if len(bars) < 2:
        return 0.0
    score = 0.0
    for previous, current in zip(bars[:-1], bars[1:]):
        if current.close > previous.close:
            score += current.volume
        elif current.close < previous.close:
            score -= current.volume
    return round(score, 2)


def sanitize_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in metrics.items():
        if isinstance(value, bool):
            sanitized[key] = value
        elif isinstance(value, Real):
            sanitized[key] = round(float(value), 4) if isfinite(value) else 0.0
        else:
            sanitized[key] = value
    return sanitized
