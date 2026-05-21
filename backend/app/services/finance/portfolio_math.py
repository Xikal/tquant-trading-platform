from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import BacktestTrade

MIN_SHARED_OBSERVATIONS = 10


def daily_strategy_return_matrix(db: Session, run_id: int) -> tuple[np.ndarray, list[str]]:
    rows = db.execute(
        select(
            BacktestTrade.trade_date,
            BacktestTrade.strategy_key,
            BacktestTrade.pnl_pct,
            BacktestTrade.pnl_amount,
            BacktestTrade.gross_amount,
            BacktestTrade.net_amount,
        )
        .where(BacktestTrade.run_id == run_id, BacktestTrade.strategy_key != "")
        .order_by(BacktestTrade.trade_date.asc())
    ).all()
    by_day: dict[str, dict[str, dict[str, Any]]] = defaultdict(
        lambda: defaultdict(lambda: {"pnl": 0.0, "exposure": 0.0, "pct_values": []})
    )
    strategies: set[str] = set()
    for trade_date, strategy_key, pnl_pct, pnl_amount, gross_amount, net_amount in rows:
        strategy = str(strategy_key or "")
        if not strategy:
            continue
        bucket = by_day[str(trade_date)][strategy]
        exposure = abs(float(gross_amount or net_amount or 0.0))
        pnl = float(pnl_amount or 0.0)
        if exposure > 0:
            bucket["pnl"] += pnl
            bucket["exposure"] += exposure
        elif pnl_pct is not None:
            bucket["pct_values"].append(float(pnl_pct) / 100.0)
        strategies.add(strategy)
    ordered_strategies = sorted(strategies)
    if not by_day or not ordered_strategies:
        return np.empty((0, 0)), []
    matrix = np.array(
        [[_strategy_daily_return(by_day[day].get(strategy)) for strategy in ordered_strategies] for day in sorted(by_day)],
        dtype=float,
    )
    return matrix, ordered_strategies


def pairwise_covariance(matrix: np.ndarray, *, min_shared_observations: int = MIN_SHARED_OBSERVATIONS) -> tuple[np.ndarray, np.ndarray]:
    count = matrix.shape[1]
    covariance = np.zeros((count, count), dtype=float)
    shared_observations = np.zeros((count, count), dtype=int)
    for left in range(count):
        for right in range(left, count):
            mask = np.isfinite(matrix[:, left]) & np.isfinite(matrix[:, right])
            shared = int(mask.sum())
            shared_observations[left, right] = shared
            shared_observations[right, left] = shared
            if left == right:
                covariance[left, right] = float(np.var(matrix[mask, left], ddof=1)) if shared >= 2 else 0.0
                continue
            covariance[left, right] = (
                float(np.cov(matrix[mask, left], matrix[mask, right], ddof=1)[0, 1])
                if shared >= min_shared_observations
                else 0.0
            )
            covariance[right, left] = covariance[left, right]
    return covariance, shared_observations


def min_shared_days(shared_observations: np.ndarray) -> int:
    if shared_observations.shape[0] < 2:
        return 0
    values = [
        int(shared_observations[left, right])
        for left in range(shared_observations.shape[0])
        for right in range(left + 1, shared_observations.shape[1])
    ]
    return min(values) if values else 0


def shared_observation_days(strategies: list[str], shared_observations: np.ndarray) -> list[dict[str, Any]]:
    return [
        {"strategy_a": strategies[left], "strategy_b": strategies[right], "shared_days": int(shared_observations[left, right])}
        for left in range(len(strategies))
        for right in range(left + 1, len(strategies))
    ]


def max_sharpe_weights(mean_returns: np.ndarray, covariance: np.ndarray, risk_free_rate: float) -> np.ndarray:
    from scipy.optimize import minimize

    count = len(mean_returns)
    initial = np.repeat(1.0 / count, count)
    bounds = [(0.0, 1.0)] * count
    constraints = ({"type": "eq", "fun": lambda weights: np.sum(weights) - 1.0},)

    def objective(weights: np.ndarray) -> float:
        _, _, sharpe = portfolio_metrics(weights, mean_returns, covariance, risk_free_rate)
        return -sharpe

    result = minimize(objective, initial, method="SLSQP", bounds=bounds, constraints=constraints)
    return normalize_weights(np.asarray(result.x, dtype=float)) if result.success else initial


def efficient_frontier(
    mean_returns: np.ndarray,
    covariance: np.ndarray,
    sample_count: int,
    risk_free_rate: float,
) -> list[dict[str, float]]:
    rng = np.random.default_rng(42)
    points: list[dict[str, float]] = []
    for _ in range(max(100, min(sample_count, 5000))):
        weights = rng.dirichlet(np.ones(len(mean_returns)))
        expected, volatility, sharpe = portfolio_metrics(weights, mean_returns, covariance, risk_free_rate)
        points.append(
            {
                "expected_return_pct": round(expected * 100, 4),
                "volatility_pct": round(volatility * 100, 4),
                "sharpe": round(sharpe, 4),
            }
        )
    points.sort(key=lambda item: (item["volatility_pct"], -item["expected_return_pct"]))
    return _thin_frontier(points)


def portfolio_metrics(
    weights: np.ndarray,
    mean_returns: np.ndarray,
    covariance: np.ndarray,
    risk_free_rate: float,
) -> tuple[float, float, float]:
    expected = float(weights @ mean_returns)
    variance = float(weights.T @ covariance @ weights)
    volatility = max(float(np.sqrt(max(variance, 0.0))), 1e-8)
    sharpe = (expected - risk_free_rate) / volatility
    return expected, volatility, sharpe


def normalize_weights(weights: np.ndarray) -> np.ndarray:
    clipped = np.clip(weights, 0.0, 1.0)
    total = float(clipped.sum())
    if total <= 0:
        return np.repeat(1.0 / len(clipped), len(clipped))
    return clipped / total


def _strategy_daily_return(bucket: dict[str, Any] | None) -> float:
    if not bucket:
        return float("nan")
    exposure = float(bucket.get("exposure") or 0.0)
    if exposure > 0:
        return float(bucket.get("pnl") or 0.0) / exposure
    pct_values = list(bucket.get("pct_values") or [])
    return float(np.mean(np.asarray(pct_values, dtype=float))) if pct_values else float("nan")


def _thin_frontier(points: list[dict[str, float]], *, limit: int = 80) -> list[dict[str, float]]:
    if len(points) <= limit:
        return points
    stride = max(int(len(points) / limit), 1)
    return points[::stride][:limit]
