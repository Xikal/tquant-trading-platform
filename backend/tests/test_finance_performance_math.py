from __future__ import annotations

import pytest

from app.models.schemas import KlineBar
from app.services.finance.performance_math import (
    annualized_sharpe_ratio,
    risk_free_rate_from_params,
    sequence_max_drawdown_pct,
)
from app.services.finance import performance_math
from app.services.indicators import atr, rsi_wilder
from app.services.finance import rust_math
from app.services.low_buy.risk_metrics import _compute_sharpe_from_returns


def test_sharpe_uses_annualized_excess_returns() -> None:
    returns = [0.01, -0.005, 0.006, 0.002]
    actual = annualized_sharpe_ratio(returns, risk_free_rate_annual_pct=2.0)
    daily_rf = 0.02 / 252
    excess = [item - daily_rf for item in returns]
    mean = sum(excess) / len(excess)
    variance = sum((item - mean) ** 2 for item in excess) / (len(excess) - 1)
    expected = (mean / (variance**0.5)) * (252**0.5)
    assert actual == pytest.approx(expected, abs=1e-12)


def test_low_buy_sharpe_path_uses_annualized_math() -> None:
    pct_returns = [1.0, -0.5, 0.6, 0.2]
    assert _compute_sharpe_from_returns(pct_returns) == pytest.approx(
        annualized_sharpe_ratio([item / 100.0 for item in pct_returns], risk_free_rate_annual_pct=2.0),
        abs=1e-12,
    )


def test_sequence_max_drawdown_respects_time_order() -> None:
    assert sequence_max_drawdown_pct([100.0, 80.0, 120.0, 110.0]) == pytest.approx(-20.0)


def test_sequence_max_drawdown_uses_rust_math_api(monkeypatch) -> None:
    monkeypatch.setattr(performance_math, "max_drawdown", lambda _: 0.25)
    assert performance_math.sequence_max_drawdown_pct([100.0, 80.0, 120.0, 110.0]) == pytest.approx(-25.0)


def test_rust_wrappers_tolerate_empty_short_none_and_nan(monkeypatch) -> None:
    monkeypatch.setattr(rust_math, "_load_rust_module", lambda: None)
    assert rust_math.rust_max_drawdown([None, float("nan"), 100.0, 90.0]) is None
    assert rust_math.rust_rolling_mean([1.0, None, 3.0], 2) is None
    assert rust_math.rust_atr_wilder([1.0], [1.0], [1.0], 14) is None
    assert rust_math.rust_vwap([1.0, None], [10.0, 20.0]) is None
    assert rust_math.rust_rank_ic([1.0, None, 2.0], [2.0, 1.0, float("nan")]) is None


def test_rust_wrappers_match_python_reference_for_migrated_metrics(monkeypatch) -> None:
    class FakeRustModule:
        @staticmethod
        def max_drawdown(values):
            peak = 0.0
            max_dd = 0.0
            for value in values:
                peak = max(peak, float(value))
                if peak > 0:
                    max_dd = max(max_dd, (peak - float(value)) / peak)
            return max_dd

        @staticmethod
        def rolling_mean(values, window):
            return [
                None if index + 1 < window else sum(values[index + 1 - window : index + 1]) / window
                for index in range(len(values))
            ]

        @staticmethod
        def rolling_std(values, window):
            result = []
            for index in range(len(values)):
                if index + 1 < window:
                    result.append(None)
                    continue
                sample = values[index + 1 - window : index + 1]
                mean = sum(sample) / len(sample)
                variance = sum((item - mean) ** 2 for item in sample) / (len(sample) - 1)
                result.append(variance**0.5)
            return result

        @staticmethod
        def volatility(values, periods_per_year):
            mean = sum(values) / len(values)
            variance = sum((item - mean) ** 2 for item in values) / (len(values) - 1)
            return variance**0.5 * periods_per_year**0.5

        @staticmethod
        def correlation(left, right):
            return _pearson(left, right)

        @staticmethod
        def beta(asset_returns, benchmark_returns):
            benchmark_mean = sum(benchmark_returns) / len(benchmark_returns)
            asset_mean = sum(asset_returns) / len(asset_returns)
            covariance = sum((a - asset_mean) * (b - benchmark_mean) for a, b in zip(asset_returns, benchmark_returns))
            variance = sum((b - benchmark_mean) ** 2 for b in benchmark_returns)
            return covariance / variance

        @staticmethod
        def bollinger_bands(values, window, num_std):
            result = []
            for index in range(len(values)):
                if index + 1 < window:
                    result.append(None)
                    continue
                sample = values[index + 1 - window : index + 1]
                mean = sum(sample) / len(sample)
                variance = sum((item - mean) ** 2 for item in sample) / (len(sample) - 1)
                std = variance**0.5
                result.append((mean + num_std * std, mean, mean - num_std * std))
            return result

        @staticmethod
        def atr_wilder(highs, lows, closes, period):
            return _python_atr_wilder(highs, lows, closes, period)

        @staticmethod
        def rsi_wilder(values, period):
            return _python_rsi_wilder(values, period)

        @staticmethod
        def vwap(prices, volumes):
            total_volume = sum(volumes)
            return sum(price * volume for price, volume in zip(prices, volumes)) / total_volume

        @staticmethod
        def rank_ic(factors, returns):
            return _spearman(factors, returns)

    monkeypatch.setattr(rust_math, "_load_rust_module", lambda: FakeRustModule)
    values = [100.0, 110.0, 104.0, 112.0, 90.0, 95.0]
    highs = [10.0, 11.0, 12.0, 11.5, 13.0, 12.0]
    lows = [9.5, 10.0, 10.5, 10.0, 11.0, 10.8]
    closes = [9.8, 10.5, 11.2, 10.7, 12.4, 11.3]
    prices = [10.0, 11.0, 12.0]
    volumes = [100.0, 120.0, 80.0]

    assert rust_math.rust_max_drawdown(values) == pytest.approx(0.1964285714)
    assert rust_math.rust_rolling_mean(values, 3) == pytest.approx([None, None, 104.6666667, 108.6666667, 102.0, 99.0])
    assert rust_math.rust_rolling_std([1.0, 2.0, 3.0, 5.0], 3) == pytest.approx([None, None, 1.0, 1.52752523])
    assert rust_math.rust_volatility([0.01, 0.02, -0.01], 252.0) == pytest.approx(0.2424871131)
    assert rust_math.rust_correlation([0.01, 0.02, -0.01], [0.02, 0.04, -0.02]) == pytest.approx(1.0)
    assert rust_math.rust_beta([0.01, 0.02, -0.01], [0.02, 0.04, -0.02]) == pytest.approx(0.5)
    assert rust_math.rust_bollinger_bands([1.0, 2.0, 3.0], 3, 2.0) == pytest.approx([None, None, (4.0, 2.0, 0.0)])
    assert rust_math.rust_atr_wilder(highs, lows, closes, 3) == pytest.approx(_python_atr_wilder(highs, lows, closes, 3))
    assert rust_math.rust_rsi_wilder(values, 3) == pytest.approx(_python_rsi_wilder(values, 3))
    assert rust_math.rust_vwap(prices, volumes) == pytest.approx(10.9333333333)
    assert rust_math.rust_rank_ic([1.0, 2.0, 3.0], [3.0, 2.0, 1.0]) == pytest.approx(-1.0)


def test_rust_rsi_wilder_flat_sequence_matches_python_reference(monkeypatch) -> None:
    class FakeRustModule:
        @staticmethod
        def rsi_wilder(values, period):
            return _python_rsi_wilder(values, period)

    monkeypatch.setattr(rust_math, "_load_rust_module", lambda: FakeRustModule)
    values = [10.0] * 16

    assert rust_math.rust_rsi_wilder(values, 14) == pytest.approx(50.0)
    assert rust_math.rust_rsi_wilder(values, 14) == pytest.approx(_python_rsi_wilder(values, 14))


def test_atr_uses_wilder_rma_not_last_sma() -> None:
    bars = [
        KlineBar(timestamp="0", open=9.5, close=9.5, high=10.0, low=9.0, volume=100, amount=1000),
        KlineBar(timestamp="1", open=9.5, close=11.0, high=12.0, low=8.0, volume=100, amount=1000),
        KlineBar(timestamp="2", open=11.0, close=12.5, high=13.0, low=12.0, volume=100, amount=1000),
        KlineBar(timestamp="3", open=12.5, close=10.5, high=12.5, low=10.0, volume=100, amount=1000),
        KlineBar(timestamp="4", open=10.5, close=15.0, high=16.0, low=14.0, volume=100, amount=1000),
        KlineBar(timestamp="5", open=15.0, close=14.0, high=15.5, low=13.5, volume=100, amount=1000),
    ]
    assert atr(bars, 3) == pytest.approx(3.1481, abs=0.0001)


def test_atr_returns_none_when_wilder_window_is_not_stable() -> None:
    bars = [
        KlineBar(timestamp=str(index), open=10.0, close=10.0, high=11.0, low=9.0, volume=100, amount=1000)
        for index in range(5)
    ]
    assert atr(bars, 3) is None


def test_rsi_wilder_is_explicit_and_stable() -> None:
    values = [44, 44.15, 43.9, 44.35, 44.8, 45.0, 44.7, 44.9, 45.2, 45.5, 45.1, 45.7, 46.0, 46.4, 46.1, 46.8]
    assert rsi_wilder(values, 14) == pytest.approx(76.6523, abs=0.0001)


def test_risk_free_rate_is_bounded_and_configurable() -> None:
    assert risk_free_rate_from_params({"risk_free_rate_annual_pct": 3.5}) == 3.5
    assert risk_free_rate_from_params({"risk_free_rate_annual_pct": 999}) == 20.0


def _python_atr_wilder(highs: list[float], lows: list[float], closes: list[float], period: int) -> list[float | None]:
    length = min(len(highs), len(lows), len(closes))
    if period <= 0 or length < period + 1:
        return [None] * length
    true_ranges = [
        max(highs[index] - lows[index], abs(highs[index] - closes[index - 1]), abs(lows[index] - closes[index - 1]))
        for index in range(1, length)
    ]
    result: list[float | None] = [None] * length
    atr_value = sum(true_ranges[:period]) / period
    result[period] = atr_value
    for index in range(period, len(true_ranges)):
        atr_value = (atr_value * (period - 1) + true_ranges[index]) / period
        result[index + 1] = atr_value
    return result


def _python_rsi_wilder(values: list[float], period: int) -> float | None:
    if len(values) < period + 1:
        return None
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
        avg_gain = ((avg_gain * (period - 1)) + max(diff, 0.0)) / period
        avg_loss = ((avg_loss * (period - 1)) + abs(min(diff, 0.0))) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _spearman(left: list[float], right: list[float]) -> float:
    left_ranks = _ranks(left)
    right_ranks = _ranks(right)
    left_mean = sum(left_ranks) / len(left_ranks)
    right_mean = sum(right_ranks) / len(right_ranks)
    covariance = sum((a - left_mean) * (b - right_mean) for a, b in zip(left_ranks, right_ranks))
    left_var = sum((a - left_mean) ** 2 for a in left_ranks)
    right_var = sum((b - right_mean) ** 2 for b in right_ranks)
    return covariance / ((left_var * right_var) ** 0.5)


def _pearson(left: list[float], right: list[float]) -> float:
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    covariance = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    left_var = sum((a - left_mean) ** 2 for a in left)
    right_var = sum((b - right_mean) ** 2 for b in right)
    return covariance / ((left_var * right_var) ** 0.5)


def _ranks(values: list[float]) -> list[float]:
    ordered = sorted((value, index) for index, value in enumerate(values))
    result = [0.0] * len(values)
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and ordered[end][0] == ordered[cursor][0]:
            end += 1
        rank = (cursor + 1 + end) / 2
        for _, index in ordered[cursor:end]:
            result[index] = rank
        cursor = end
    return result
