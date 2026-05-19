from __future__ import annotations

import pytest

from app.models.schemas import KlineBar
from app.services.finance.performance_math import (
    annualized_sharpe_ratio,
    risk_free_rate_from_params,
    sequence_max_drawdown_pct,
)
from app.services.indicators import atr


def test_sharpe_uses_annualized_excess_returns() -> None:
    returns = [0.01, -0.005, 0.006, 0.002]
    actual = annualized_sharpe_ratio(returns, risk_free_rate_annual_pct=2.0)
    daily_rf = 0.02 / 252
    excess = [item - daily_rf for item in returns]
    mean = sum(excess) / len(excess)
    variance = sum((item - mean) ** 2 for item in excess) / (len(excess) - 1)
    expected = (mean / (variance**0.5)) * (252**0.5)
    assert actual == pytest.approx(expected, abs=1e-12)


def test_sequence_max_drawdown_respects_time_order() -> None:
    assert sequence_max_drawdown_pct([100.0, 80.0, 120.0, 110.0]) == pytest.approx(-20.0)


def test_atr_uses_wilder_rma_not_last_sma() -> None:
    bars = [
        KlineBar(timestamp="0", open=9.5, close=9.5, high=10.0, low=9.0, volume=100, amount=1000),
        KlineBar(timestamp="1", open=9.5, close=11.0, high=12.0, low=8.0, volume=100, amount=1000),
        KlineBar(timestamp="2", open=11.0, close=12.5, high=13.0, low=12.0, volume=100, amount=1000),
        KlineBar(timestamp="3", open=12.5, close=10.5, high=12.5, low=10.0, volume=100, amount=1000),
        KlineBar(timestamp="4", open=10.5, close=15.0, high=16.0, low=14.0, volume=100, amount=1000),
    ]
    assert atr(bars, 3) == pytest.approx(3.7222, abs=0.0001)


def test_risk_free_rate_is_bounded_and_configurable() -> None:
    assert risk_free_rate_from_params({"risk_free_rate_annual_pct": 3.5}) == 3.5
    assert risk_free_rate_from_params({"risk_free_rate_annual_pct": 999}) == 20.0

