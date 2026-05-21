from __future__ import annotations

from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.services.finance.portfolio_math import (
    MIN_SHARED_OBSERVATIONS,
    daily_strategy_return_matrix,
    efficient_frontier,
    max_sharpe_weights,
    min_shared_days,
    pairwise_covariance,
    portfolio_metrics,
    shared_observation_days,
)

_daily_strategy_return_matrix = daily_strategy_return_matrix


def optimize_markowitz_portfolio(
    db: Session,
    run_id: int,
    *,
    risk_free_rate_pct: float = 0.0,
    monte_carlo_samples: int = 1200,
) -> dict[str, Any]:
    matrix, strategies = daily_strategy_return_matrix(db, run_id)
    if matrix.size == 0 or len(strategies) < 2:
        return _empty(run_id, "策略成交样本不足，至少需要 2 个策略的历史收益序列。")
    valid_counts = np.isfinite(matrix).sum(axis=0)
    active_mask = valid_counts > 0
    if int(active_mask.sum()) < 2:
        return _empty(run_id, "策略成交样本不足，至少需要 2 个策略存在有效收益。")
    matrix = matrix[:, active_mask]
    strategies = [strategy for strategy, active in zip(strategies, active_mask) if bool(active)]
    valid_counts = valid_counts[active_mask]
    mean_returns = np.nanmean(matrix, axis=0)
    covariance, shared_observations = pairwise_covariance(matrix)
    min_days = min_shared_days(shared_observations)
    if min_days < MIN_SHARED_OBSERVATIONS:
        result = _empty(
            run_id,
            f"策略共同成交日不足：最少 {min_days} 天，低于 {MIN_SHARED_OBSERVATIONS} 天门槛，暂不生成均值-方差权重。",
        )
        result["min_shared_days_per_pair"] = min_days
        result["shared_observation_days"] = shared_observation_days(strategies, shared_observations)
        return result
    covariance = np.atleast_2d(covariance) + np.eye(len(strategies)) * 1e-8
    risk_free_rate = risk_free_rate_pct / 100.0
    weights = max_sharpe_weights(mean_returns, covariance, risk_free_rate)
    expected, volatility, sharpe = portfolio_metrics(weights, mean_returns, covariance, risk_free_rate)
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
        "min_shared_days_per_pair": min_days,
        "shared_observation_days": shared_observation_days(strategies, shared_observations),
        "expected_return_pct": round(expected * 100, 4),
        "volatility_pct": round(volatility * 100, 4),
        "portfolio_sharpe": round(sharpe, 4),
        "efficient_frontier": efficient_frontier(mean_returns, covariance, monte_carlo_samples, risk_free_rate),
        "summary": "研究用途：基于策略共同成交日的收益协方差生成风险-收益权重，不自动用于实盘或模拟盘。",
    }


def _empty(run_id: int, summary: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "method": "markowitz",
        "method_label": "Markowitz 均值-方差优化",
        "weights": [],
        "efficient_frontier": [],
        "summary": summary,
    }
