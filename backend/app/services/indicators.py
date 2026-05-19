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


def bollinger_bands(values: list[float], window: int = 20, num_std: float = 2.0) -> tuple[float, float, float]:
    """Return upper/middle/lower Bollinger Bands using sample standard deviation."""

    clean = [float(value) for value in values if isinstance(value, Real) and isfinite(float(value))]
    if not clean:
        return (0.0, 0.0, 0.0)
    window = max(1, int(window or 1))
    sample = clean[-window:]
    middle = sum(sample) / len(sample)
    if len(sample) < 2:
        std = 0.0
    else:
        variance = sum((value - middle) ** 2 for value in sample) / (len(sample) - 1)
        std = variance ** 0.5
    upper = middle + float(num_std) * std
    lower = middle - float(num_std) * std
    return round(upper, 4), round(middle, 4), round(lower, 4)


def stochastic(bars: list[KlineBar], k_period: int = 14, d_period: int = 3) -> tuple[float, float]:
    """Return %K and %D. %D is a configurable SMA of recent %K values."""

    k_period = max(1, int(k_period or 1))
    d_period = max(1, int(d_period or 1))
    if len(bars) < k_period:
        return (50.0, 50.0)
    k_values: list[float] = []
    start = max(k_period - 1, len(bars) - d_period)
    for index in range(start, len(bars)):
        window = bars[index - k_period + 1 : index + 1]
        lowest = min(bar.low for bar in window)
        highest = max(bar.high for bar in window)
        close = window[-1].close
        if highest <= lowest:
            k_values.append(50.0)
        else:
            k_values.append((close - lowest) / (highest - lowest) * 100)
    latest_k = k_values[-1]
    latest_d = sum(k_values[-d_period:]) / min(d_period, len(k_values))
    return round(latest_k, 4), round(latest_d, 4)


def vwap(bars: list[KlineBar]) -> float:
    bars = _latest_session_bars(bars)
    total_turnover = 0.0
    total_volume = 0.0
    for bar in bars:
        typical_price = (bar.high + bar.low + bar.close) / 3
        total_turnover += typical_price * max(bar.volume, 1)
        total_volume += max(bar.volume, 1)
    if total_volume == 0:
        return 0.0
    return round(total_turnover / total_volume, 4)


def _latest_session_bars(bars: list[KlineBar]) -> list[KlineBar]:
    """Use only the latest trading day when timestamps carry date information."""

    if not bars:
        return []
    latest_key = _session_key(bars[-1])
    if not latest_key:
        return bars
    filtered = [bar for bar in bars if _session_key(bar) == latest_key]
    return filtered or bars


def _session_key(bar: KlineBar) -> str:
    raw = str(getattr(bar, "timestamp", "") or "")
    if len(raw) >= 10 and raw[4] in "-/" and raw[7] in "-/":
        return raw[:10].replace("/", "-")
    return ""


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
