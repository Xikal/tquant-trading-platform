from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import BacktestTrade


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
    mean_returns = matrix.mean(axis=0)
    covariance = np.cov(matrix, rowvar=False)
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
                "sample_count": int((matrix[:, index] != 0).sum()),
            }
            for index, strategy in enumerate(strategies)
        ],
        "expected_return_pct": round(expected * 100, 4),
        "volatility_pct": round(volatility * 100, 4),
        "portfolio_sharpe": round(sharpe, 4),
        "efficient_frontier": frontier,
        "summary": "研究用途：基于历史成交收益协方差生成风险-收益权重，不自动用于实盘或模拟盘。",
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
        return 0.0
    exposure = float(bucket.get("exposure") or 0.0)
    if exposure > 0:
        return float(bucket.get("pnl") or 0.0) / exposure
    pct_values = list(bucket.get("pct_values") or [])
    if not pct_values:
        return 0.0
    return float(np.mean(np.asarray(pct_values, dtype=float)))


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
