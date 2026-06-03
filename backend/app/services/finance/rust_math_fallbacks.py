from __future__ import annotations

import math
from collections.abc import Sequence


def optional_float_list(values: Sequence[object]) -> list[float | None]:
    return [None if value is None else float(value) for value in values]


def finite_float_list(values: Sequence[object]) -> list[float]:
    result: list[float] = []
    for item in values:
        try:
            value = float(item)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            result.append(value)
    return result


def float_list_or_none(values: Sequence[object]) -> list[float] | None:
    result: list[float] = []
    for item in values:
        try:
            value = float(item)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(value):
            return None
        result.append(value)
    return result


def finite_pairs(left: Sequence[object], right: Sequence[object]) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    for left_item, right_item in zip(left, right):
        try:
            left_value = float(left_item)
            right_value = float(right_item)
        except (TypeError, ValueError):
            continue
        if math.isfinite(left_value) and math.isfinite(right_value):
            pairs.append((left_value, right_value))
    return pairs


def max_drawdown(equity: Sequence[object]) -> float:
    values = finite_float_list(equity)
    if not values:
        return 0.0
    peak = values[0]
    max_dd = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            max_dd = max(max_dd, (peak - value) / peak)
    return max_dd


def rolling_mean(values: Sequence[object], window: int) -> list[float | None]:
    cleaned = float_list_or_none(values)
    if cleaned is None:
        return [None] * len(values)
    window = int(window)
    if window <= 0:
        return [None] * len(cleaned)
    result: list[float | None] = []
    running_sum = 0.0
    for index, value in enumerate(cleaned):
        running_sum += value
        if index >= window:
            running_sum -= cleaned[index - window]
        result.append(running_sum / window if index + 1 >= window else None)
    return result


def rolling_std(values: Sequence[object], window: int) -> list[float | None]:
    cleaned = float_list_or_none(values)
    if cleaned is None:
        return [None] * len(values)
    window = int(window)
    if window <= 0:
        return [None] * len(cleaned)
    result: list[float | None] = []
    running_sum = 0.0
    running_sum_sq = 0.0
    for index, value in enumerate(cleaned):
        running_sum += value
        running_sum_sq += value * value
        if index >= window:
            old = cleaned[index - window]
            running_sum -= old
            running_sum_sq -= old * old
        result.append(sample_std_from_sums(running_sum, running_sum_sq, window) if index + 1 >= window else None)
    return result


def atr_wilder(
    highs: Sequence[object],
    lows: Sequence[object],
    closes: Sequence[object],
    period: int,
) -> list[float | None]:
    high_values = float_list_or_none(highs)
    low_values = float_list_or_none(lows)
    close_values = float_list_or_none(closes)
    length = min(len(highs), len(lows), len(closes))
    if high_values is None or low_values is None or close_values is None:
        return [None] * length
    length = min(len(high_values), len(low_values), len(close_values))
    period = int(period)
    if period <= 0 or length < period + 1:
        return [None] * length
    true_ranges = [
        max(
            high_values[index] - low_values[index],
            abs(high_values[index] - close_values[index - 1]),
            abs(low_values[index] - close_values[index - 1]),
        )
        for index in range(1, length)
    ]
    result: list[float | None] = [None] * length
    atr_value = sum(true_ranges[:period]) / period
    result[period] = atr_value
    for index in range(period, len(true_ranges)):
        atr_value = (atr_value * (period - 1) + true_ranges[index]) / period
        result[index + 1] = atr_value
    return result


def rsi_wilder(values: Sequence[object], period: int) -> float | None:
    cleaned = float_list_or_none(values)
    period = int(period)
    if cleaned is None or period <= 0 or len(cleaned) <= period:
        return None
    gains = 0.0
    losses = 0.0
    for index in range(1, period + 1):
        delta = cleaned[index] - cleaned[index - 1]
        if delta >= 0:
            gains += delta
        else:
            losses += -delta
    avg_gain = gains / period
    avg_loss = losses / period
    for index in range(period + 1, len(cleaned)):
        delta = cleaned[index] - cleaned[index - 1]
        gain = delta if delta > 0 else 0.0
        loss = -delta if delta < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def vwap(prices: Sequence[object], volumes: Sequence[object]) -> float | None:
    pairs = finite_pairs(prices, volumes)
    if not pairs:
        return None
    total_turnover = 0.0
    total_volume = 0.0
    for price, volume in pairs:
        clean_volume = max(volume, 0.0)
        total_turnover += price * clean_volume
        total_volume += clean_volume
    if total_volume <= 0:
        return None
    return total_turnover / total_volume


def bollinger_bands(
    values: Sequence[object],
    window: int,
    num_std: float,
) -> list[tuple[float, float, float] | None]:
    means = rolling_mean(values, window)
    stds = rolling_std(values, window)
    result: list[tuple[float, float, float] | None] = []
    for mean, std in zip(means, stds):
        if mean is None or std is None:
            result.append(None)
            continue
        result.append((mean + float(num_std) * std, mean, mean - float(num_std) * std))
    return result


def beta(asset_returns: Sequence[object], benchmark_returns: Sequence[object]) -> float | None:
    pairs = finite_pairs(asset_returns, benchmark_returns)
    if len(pairs) < 2:
        return None
    assets = [item[0] for item in pairs]
    benchmarks = [item[1] for item in pairs]
    asset_mean = sum(assets) / len(assets)
    benchmark_mean = sum(benchmarks) / len(benchmarks)
    covariance = sum((asset - asset_mean) * (benchmark - benchmark_mean) for asset, benchmark in pairs)
    benchmark_var = sum((benchmark - benchmark_mean) ** 2 for benchmark in benchmarks)
    if benchmark_var <= 0:
        return None
    return covariance / benchmark_var


def correlation(left: Sequence[object], right: Sequence[object]) -> float | None:
    pairs = finite_pairs(left, right)
    if len(pairs) < 2:
        return None
    left_values = [item[0] for item in pairs]
    right_values = [item[1] for item in pairs]
    return pearson(left_values, right_values)


def rank_ic(factors: Sequence[object], returns: Sequence[object]) -> float | None:
    pairs = finite_pairs(factors, returns)
    if len(pairs) < 2:
        return None
    factor_ranks = ranks([item[0] for item in pairs])
    return_ranks = ranks([item[1] for item in pairs])
    return pearson(factor_ranks, return_ranks)


def volatility(returns: Sequence[object], periods_per_year: float = 252.0) -> float | None:
    cleaned = float_list_or_none(returns)
    if cleaned is None or len(cleaned) < 2:
        return None
    return sample_std(cleaned) * math.sqrt(max(float(periods_per_year), 1.0))


def pearson(left: Sequence[float], right: Sequence[float]) -> float | None:
    length = min(len(left), len(right))
    if length < 2:
        return None
    left_values = list(left[:length])
    right_values = list(right[:length])
    left_mean = sum(left_values) / length
    right_mean = sum(right_values) / length
    covariance = 0.0
    left_var = 0.0
    right_var = 0.0
    for left_value, right_value in zip(left_values, right_values):
        left_delta = left_value - left_mean
        right_delta = right_value - right_mean
        covariance += left_delta * right_delta
        left_var += left_delta * left_delta
        right_var += right_delta * right_delta
    if left_var <= 0 or right_var <= 0:
        return None
    return covariance / math.sqrt(left_var * right_var)


def sample_std(values: Sequence[float]) -> float:
    return sample_std_from_sums(sum(values), sum(value * value for value in values), len(values))


def sample_std_from_sums(total: float, total_sq: float, length: int) -> float:
    if length < 2:
        return 0.0
    n = float(length)
    variance = max((total_sq - (total * total / n)) / (n - 1.0), 0.0)
    return math.sqrt(variance)


def ranks(values: Sequence[float]) -> list[float]:
    pairs = sorted((float(value), index) for index, value in enumerate(values))
    result = [0.0] * len(values)
    cursor = 0
    while cursor < len(pairs):
        end = cursor + 1
        while end < len(pairs) and pairs[end][0] == pairs[cursor][0]:
            end += 1
        rank = (cursor + 1 + end) / 2
        for _value, index in pairs[cursor:end]:
            result[index] = rank
        cursor = end
    return result
