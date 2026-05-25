from __future__ import annotations

from math import sqrt
from typing import Iterable

from app.services.finance.rust_math import rust_max_drawdown


TRADING_DAYS_PER_YEAR = 252
DEFAULT_RISK_FREE_RATE_ANNUAL_PCT = 2.0


def annualized_sharpe_ratio(
    returns: Iterable[float],
    *,
    risk_free_rate_annual_pct: float = DEFAULT_RISK_FREE_RATE_ANNUAL_PCT,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    values = list(returns)
    if len(values) < 2:
        return 0.0
    daily_rf = risk_free_rate_annual_pct / 100.0 / max(periods_per_year, 1)
    excess = [item - daily_rf for item in values]
    mean = sum(excess) / len(excess)
    variance = sum((item - mean) ** 2 for item in excess) / (len(excess) - 1)
    if variance <= 0:
        return 0.0
    return (mean / sqrt(variance)) * sqrt(periods_per_year)


def annualized_sortino_ratio(
    returns: Iterable[float],
    *,
    risk_free_rate_annual_pct: float = DEFAULT_RISK_FREE_RATE_ANNUAL_PCT,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    values = list(returns)
    if len(values) < 2:
        return 0.0
    daily_rf = risk_free_rate_annual_pct / 100.0 / max(periods_per_year, 1)
    excess = [item - daily_rf for item in values]
    mean = sum(excess) / len(excess)
    downside = [min(item, 0.0) for item in excess]
    downside_deviation = sqrt(sum(item**2 for item in downside) / len(excess))
    if downside_deviation <= 0:
        return 0.0
    return (mean / downside_deviation) * sqrt(periods_per_year)


def sequence_max_drawdown_pct(equity_values: Iterable[float]) -> float:
    values = list(equity_values)
    if not values:
        return 0.0
    rust_value = rust_max_drawdown(values)
    if rust_value is not None:
        return -float(rust_value) * 100.0
    peak = 0.0
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = min(max_drawdown, (value - peak) / peak * 100)
    return max_drawdown


def risk_free_rate_from_params(params: dict[str, object] | None) -> float:
    if not params:
        return DEFAULT_RISK_FREE_RATE_ANNUAL_PCT
    try:
        value = float(params.get("risk_free_rate_annual_pct", DEFAULT_RISK_FREE_RATE_ANNUAL_PCT))
    except (TypeError, ValueError):
        return DEFAULT_RISK_FREE_RATE_ANNUAL_PCT
    return max(0.0, min(value, 20.0))
