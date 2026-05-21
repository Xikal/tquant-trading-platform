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


def optimize_black_litterman_portfolio(
    db: Session,
    run_id: int,
    *,
    risk_free_rate_pct: float = 0.0,
    tau: float = 0.05,
    view_confidence: float = 0.60,
    monte_carlo_samples: int = 1200,
) -> dict[str, Any]:
    matrix, strategies = daily_strategy_return_matrix(db, run_id)
    if matrix.size == 0 or len(strategies) < 2:
        return _empty(run_id, "策略成交样本不足，至少需要 2 个策略的历史收益序列。")

    active_mask = np.isfinite(matrix).sum(axis=0) > 0
    if int(active_mask.sum()) < 2:
        return _empty(run_id, "策略有效收益不足，暂不生成 Black-Litterman 权重。")

    matrix = matrix[:, active_mask]
    strategies = [strategy for strategy, active in zip(strategies, active_mask) if bool(active)]
    valid_counts = np.isfinite(matrix).sum(axis=0)
    sample_means = np.nanmean(matrix, axis=0)
    covariance, shared = pairwise_covariance(matrix)
    min_days = min_shared_days(shared)
    if min_days < MIN_SHARED_OBSERVATIONS:
        result = _empty(run_id, f"策略共同成交日不足：最少 {min_days} 天，低于 {MIN_SHARED_OBSERVATIONS} 天门槛。")
        result["min_shared_days_per_pair"] = min_days
        result["shared_observation_days"] = shared_observation_days(strategies, shared)
        return result

    covariance = np.atleast_2d(covariance) + np.eye(len(strategies)) * 1e-8
    posterior_returns = _posterior_returns(sample_means, covariance, tau=max(tau, 1e-4), view_confidence=view_confidence)
    weights = max_sharpe_weights(posterior_returns, covariance, risk_free_rate_pct / 100.0)
    expected, volatility, sharpe = portfolio_metrics(weights, posterior_returns, covariance, risk_free_rate_pct / 100.0)
    frontier = efficient_frontier(posterior_returns, covariance, monte_carlo_samples, risk_free_rate_pct / 100.0)
    return {
        "run_id": run_id,
        "method": "black_litterman",
        "method_label": "Black-Litterman 组合优化",
        "weights": [
            {
                "strategy_key": strategy,
                "weight_pct": round(float(weights[index]) * 100, 2),
                "posterior_return_pct": round(float(posterior_returns[index]) * 100, 4),
                "sample_avg_return_pct": round(float(sample_means[index]) * 100, 4),
                "volatility_pct": round(float(np.sqrt(covariance[index, index])) * 100, 4),
                "sample_count": int(valid_counts[index]),
            }
            for index, strategy in enumerate(strategies)
        ],
        "expected_return_pct": round(expected * 100, 4),
        "volatility_pct": round(volatility * 100, 4),
        "portfolio_sharpe": round(sharpe, 4),
        "efficient_frontier": frontier,
        "min_shared_days_per_pair": min_days,
        "shared_observation_days": shared_observation_days(strategies, shared),
        "summary": "研究用途：用样本均值作为观点、协方差作为先验不确定性生成 BL 后验收益，不自动用于真实交易。",
    }


def _posterior_returns(sample_means: np.ndarray, covariance: np.ndarray, *, tau: float, view_confidence: float) -> np.ndarray:
    count = len(sample_means)
    market_weights = np.repeat(1.0 / count, count)
    risk_aversion = 2.5
    equilibrium = risk_aversion * covariance @ market_weights
    p_matrix = np.eye(count)
    confidence = max(0.05, min(float(view_confidence), 0.95))
    omega_diag = np.maximum(np.diag(tau * covariance) / confidence, 1e-8)
    omega_inv = np.diag(1.0 / omega_diag)
    prior_inv = np.linalg.pinv(tau * covariance)
    middle = prior_inv + p_matrix.T @ omega_inv @ p_matrix
    right = prior_inv @ equilibrium + p_matrix.T @ omega_inv @ sample_means
    return np.linalg.pinv(middle) @ right


def _empty(run_id: int, summary: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "method": "black_litterman",
        "method_label": "Black-Litterman 组合优化",
        "weights": [],
        "efficient_frontier": [],
        "summary": summary,
    }
