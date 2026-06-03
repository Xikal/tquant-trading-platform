from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.finance import rust_math
from app.services.finance import rust_math_fallbacks as fallback


class _FakeRustModule:
    @staticmethod
    def max_drawdown(values):
        return fallback.max_drawdown(values)

    @staticmethod
    def rolling_mean(values, window):
        return fallback.rolling_mean(values, window)

    @staticmethod
    def rolling_std(values, window):
        return fallback.rolling_std(values, window)

    @staticmethod
    def volatility(values, periods_per_year):
        return fallback.volatility(values, periods_per_year)

    @staticmethod
    def correlation(left, right):
        return fallback.correlation(left, right)

    @staticmethod
    def beta(asset_returns, benchmark_returns):
        return fallback.beta(asset_returns, benchmark_returns)

    @staticmethod
    def bollinger_bands(values, window, num_std):
        return fallback.bollinger_bands(values, window, num_std)

    @staticmethod
    def atr_wilder(highs, lows, closes, period):
        return fallback.atr_wilder(highs, lows, closes, period)

    @staticmethod
    def rsi_wilder(values, period):
        return fallback.rsi_wilder(values, period)

    @staticmethod
    def vwap(prices, volumes):
        return fallback.vwap(prices, volumes)

    @staticmethod
    def rank_ic(factors, returns):
        return fallback.rank_ic(factors, returns)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    with rust_math._DERIVED_CACHE_LOCK:
        rust_math._DERIVED_CACHE.clear()


def test_high_level_api_matches_rust_wrappers_and_python_fallback(monkeypatch) -> None:
    values = [100.0, 110.0, 104.0, 112.0, 90.0, 95.0]
    highs = [10.0, 11.0, 12.0, 11.5, 13.0, 12.0]
    lows = [9.5, 10.0, 10.5, 10.0, 11.0, 10.8]
    closes = [9.8, 10.5, 11.2, 10.7, 12.4, 11.3]
    prices = [10.0, 11.0, 12.0]
    volumes = [100.0, 120.0, 80.0]

    monkeypatch.setattr(rust_math, "get_settings", lambda: SimpleNamespace(rust_finance_math_enabled=True))
    monkeypatch.setattr(rust_math, "_load_rust_module", lambda: _FakeRustModule)
    rust_outputs = _api_outputs(values, highs, lows, closes, prices, volumes)

    with rust_math._DERIVED_CACHE_LOCK:
        rust_math._DERIVED_CACHE.clear()
    monkeypatch.setattr(rust_math, "get_settings", lambda: SimpleNamespace(rust_finance_math_enabled=False))
    python_outputs = _api_outputs(values, highs, lows, closes, prices, volumes)

    assert python_outputs["max_drawdown"] == pytest.approx(rust_outputs["max_drawdown"], abs=1e-9)
    assert python_outputs["rolling_mean"] == pytest.approx(rust_outputs["rolling_mean"], abs=1e-9)
    assert python_outputs["rolling_std"] == pytest.approx(rust_outputs["rolling_std"], abs=1e-9)
    assert python_outputs["atr"] == pytest.approx(rust_outputs["atr"], abs=1e-9)
    assert python_outputs["rsi_wilder"] == pytest.approx(rust_outputs["rsi_wilder"], abs=1e-9)
    assert python_outputs["vwap"] == pytest.approx(rust_outputs["vwap"], abs=1e-9)
    assert python_outputs["bollinger_bands"] == pytest.approx(rust_outputs["bollinger_bands"], abs=1e-9)
    assert python_outputs["beta"] == pytest.approx(rust_outputs["beta"], abs=1e-9)
    assert python_outputs["correlation"] == pytest.approx(rust_outputs["correlation"], abs=1e-9)
    assert python_outputs["rank_ic"] == pytest.approx(rust_outputs["rank_ic"], abs=1e-9)
    assert python_outputs["volatility"] == pytest.approx(rust_outputs["volatility"], abs=1e-9)


def test_high_level_api_uses_cache_metrics(monkeypatch) -> None:
    monkeypatch.setattr(rust_math, "get_settings", lambda: SimpleNamespace(rust_finance_math_enabled=False))
    before = rust_math.rust_math_metrics_snapshot()

    assert rust_math.rolling_mean([1.0, 2.0, 3.0], 2) == [None, 1.5, 2.5]
    assert rust_math.rolling_mean([1.0, 2.0, 3.0], 2) == [None, 1.5, 2.5]

    after = rust_math.rust_math_metrics_snapshot()
    assert after["cache_misses"] >= before["cache_misses"] + 1
    assert after["cache_hits"] >= before["cache_hits"] + 1
    assert after["cache_size"] >= 1


def test_high_level_api_skips_cache_for_large_inputs(monkeypatch) -> None:
    monkeypatch.setattr(rust_math, "get_settings", lambda: SimpleNamespace(rust_finance_math_enabled=False))
    values = [float(index) for index in range(rust_math._DERIVED_CACHE_MAX_INPUT_POINTS + 1)]
    before = rust_math.rust_math_metrics_snapshot()

    assert rust_math.rolling_mean(values, 20)[-1] == pytest.approx(502.5)
    assert rust_math.rolling_mean(values, 20)[-1] == pytest.approx(502.5)

    after = rust_math.rust_math_metrics_snapshot()
    assert after["cache_hits"] == before["cache_hits"]
    assert after["cache_misses"] == before["cache_misses"]
    assert after["cache_size"] == before["cache_size"]


def _api_outputs(values, highs, lows, closes, prices, volumes):  # noqa: ANN001
    return {
        "max_drawdown": rust_math.max_drawdown(values),
        "rolling_mean": rust_math.rolling_mean(values, 3),
        "rolling_std": rust_math.rolling_std([1.0, 2.0, 3.0, 5.0], 3),
        "atr": rust_math.atr(highs, lows, closes, 3),
        "rsi_wilder": rust_math.rsi_wilder(values, 3),
        "vwap": rust_math.vwap(prices, volumes),
        "bollinger_bands": rust_math.bollinger_bands([1.0, 2.0, 3.0], 3, 2.0),
        "beta": rust_math.beta([0.01, 0.02, -0.01], [0.02, 0.04, -0.02]),
        "correlation": rust_math.correlation([0.01, 0.02, -0.01], [0.02, 0.04, -0.02]),
        "rank_ic": rust_math.rank_ic([1.0, 2.0, 3.0], [3.0, 2.0, 1.0]),
        "volatility": rust_math.volatility([0.01, 0.02, -0.01], 252.0),
    }
