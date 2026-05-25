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


def test_sequence_max_drawdown_uses_rust_fallback_when_available(monkeypatch) -> None:
    monkeypatch.setattr(performance_math, "rust_max_drawdown", lambda _: 0.25)
    assert performance_math.sequence_max_drawdown_pct([100.0, 80.0, 120.0, 110.0]) == pytest.approx(-25.0)


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
