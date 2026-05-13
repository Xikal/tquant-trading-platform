from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import BacktestTrade

MIN_SHARED_OBSERVATIONS = 10


def optimize_markowitz_portfolio(
    db: Session,
    run_id: int,
    *,
    risk_free_rate_pct: float = 0.0,
    monte_carlo_samples: int = 1200,
) -> dict[str, Any]:
    matrix, strategies = _daily_strategy_return_matrix(db, run_id)
    if matrix.size == 0 or len(strategies) < 2:
        return {
            "run_id": run_id,
            "method": "markowitz",
            "weights": [],
            "efficient_frontier": [],
            "summary": "策略成交样本不足，至少需要 2 个策略的历史收益序列。",
        }
    valid_counts = np.isfinite(matrix).sum(axis=0)
    active_mask = valid_counts > 0
    if int(active_mask.sum()) < 2:
        return {
            "run_id": run_id,
            "method": "markowitz",
            "weights": [],
            "efficient_frontier": [],
            "summary": "策略成交样本不足，至少需要 2 个策略存在有效收益。",
        }
    matrix = matrix[:, active_mask]
    strategies = [strategy for strategy, active in zip(strategies, active_mask) if bool(active)]
    valid_counts = valid_counts[active_mask]
    mean_returns = np.nanmean(matrix, axis=0)
    covariance, shared_observations = _pairwise_covariance(matrix)
    min_shared_days = _min_shared_days(shared_observations)
    if min_shared_days < MIN_SHARED_OBSERVATIONS:
        return {
            "run_id": run_id,
            "method": "markowitz",
            "method_label": "Markowitz 均值-方差优化",
            "weights": [],
            "efficient_frontier": [],
            "min_shared_days_per_pair": min_shared_days,
            "shared_observation_days": _shared_observation_days(strategies, shared_observations),
            "summary": f"策略共同成交日不足：最少 {min_shared_days} 天，低于 {MIN_SHARED_OBSERVATIONS} 天门槛，暂不生成均值-方差权重。",
        }
    covariance = np.atleast_2d(covariance) + np.eye(len(strategies)) * 1e-8
    weights = _max_sharpe_weights(mean_returns, covariance, risk_free_rate_pct / 100.0)
    expected, volatility, sharpe = _portfolio_metrics(weights, mean_returns, covariance, risk_free_rate_pct / 100.0)
    frontier = _efficient_frontier(mean_returns, covariance, monte_carlo_samples, risk_free_rate_pct / 100.0)
    return {
        "run_id": run_id,
        "method": "markowitz",
        "method_label": "Markowitz 均值-方差优化",
        "weights": [
            {
                "strategy_key": strategy,
                "weight_pct": round(float(weights[index]) * 100, 2),
                "avg_return_pct": round(float(mean_returns[index]) * 100, 4),
                "volatility_pct": round(float(np.sqrt(covariance[index, index])) * 100, 4),
                "sample_count": int(valid_counts[index]),
            }
            for index, strategy in enumerate(strategies)
        ],
        "min_shared_days_per_pair": min_shared_days,
        "shared_observation_days": _shared_observation_days(strategies, shared_observations),
        "expected_return_pct": round(expected * 100, 4),
        "volatility_pct": round(volatility * 100, 4),
        "portfolio_sharpe": round(sharpe, 4),
        "efficient_frontier": frontier,
        "summary": "研究用途：基于策略共同成交日的收益协方差生成风险-收益权重，不自动用于实盘或模拟盘。",
    }


def _daily_strategy_return_matrix(db: Session, run_id: int) -> tuple[np.ndarray, list[str]]:
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


def _strategy_daily_return(bucket: dict[str, Any] | None) -> float:
    if not bucket:
        return float("nan")
    exposure = float(bucket.get("exposure") or 0.0)
    if exposure > 0:
        return float(bucket.get("pnl") or 0.0) / exposure
    pct_values = list(bucket.get("pct_values") or [])
    if not pct_values:
        return float("nan")
    return float(np.mean(np.asarray(pct_values, dtype=float)))


def _pairwise_covariance(matrix: np.ndarray, *, min_shared_observations: int = MIN_SHARED_OBSERVATIONS) -> tuple[np.ndarray, np.ndarray]:
    """Return pairwise covariance using only days where both strategies traded."""

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
            if shared >= min_shared_observations:
                pair_cov = float(np.cov(matrix[mask, left], matrix[mask, right], ddof=1)[0, 1])
            else:
                pair_cov = 0.0
            covariance[left, right] = pair_cov
            covariance[right, left] = pair_cov
    return covariance, shared_observations


def _min_shared_days(shared_observations: np.ndarray) -> int:
    if shared_observations.shape[0] < 2:
        return 0
    values = [
        int(shared_observations[left, right])
        for left in range(shared_observations.shape[0])
        for right in range(left + 1, shared_observations.shape[1])
    ]
    return min(values) if values else 0


def _shared_observation_days(strategies: list[str], shared_observations: np.ndarray) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for left in range(len(strategies)):
        for right in range(left + 1, len(strategies)):
            pairs.append(
                {
                    "strategy_a": strategies[left],
                    "strategy_b": strategies[right],
                    "shared_days": int(shared_observations[left, right]),
                }
            )
    return pairs


def _max_sharpe_weights(mean_returns: np.ndarray, covariance: np.ndarray, risk_free_rate: float) -> np.ndarray:
    from scipy.optimize import minimize

    count = len(mean_returns)
    initial = np.repeat(1.0 / count, count)
    bounds = [(0.0, 1.0)] * count
    constraints = ({"type": "eq", "fun": lambda weights: np.sum(weights) - 1.0},)

    def objective(weights: np.ndarray) -> float:
        _, _, sharpe = _portfolio_metrics(weights, mean_returns, covariance, risk_free_rate)
        return -sharpe

    result = minimize(objective, initial, method="SLSQP", bounds=bounds, constraints=constraints)
    if not result.success:
        return initial
    return _normalize_weights(np.asarray(result.x, dtype=float))


def _efficient_frontier(
    mean_returns: np.ndarray,
    covariance: np.ndarray,
    sample_count: int,
    risk_free_rate: float,
) -> list[dict[str, float]]:
    rng = np.random.default_rng(42)
    points: list[dict[str, float]] = []
    for _ in range(max(100, min(sample_count, 5000))):
        weights = rng.dirichlet(np.ones(len(mean_returns)))
        expected, volatility, sharpe = _portfolio_metrics(weights, mean_returns, covariance, risk_free_rate)
        points.append(
            {
                "expected_return_pct": round(expected * 100, 4),
                "volatility_pct": round(volatility * 100, 4),
                "sharpe": round(sharpe, 4),
            }
        )
    points.sort(key=lambda item: (item["volatility_pct"], -item["expected_return_pct"]))
    return _thin_frontier(points)


def _portfolio_metrics(
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


def _normalize_weights(weights: np.ndarray) -> np.ndarray:
    clipped = np.clip(weights, 0.0, 1.0)
    total = float(clipped.sum())
    if total <= 0:
        return np.repeat(1.0 / len(clipped), len(clipped))
    return clipped / total


def _thin_frontier(points: list[dict[str, float]], *, limit: int = 80) -> list[dict[str, float]]:
    if len(points) <= limit:
        return points
    stride = max(int(len(points) / limit), 1)
    return points[::stride][:limit]
