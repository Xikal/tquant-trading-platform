from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import numpy as np
from scipy.optimize import minimize
from sqlalchemy.orm import Session

from app.services.low_buy.strategy_parameter_defaults_parts.runtime import PAPER_RISK_CONTROL_DEFAULTS
from app.services.paper.performance import PaperPerformanceService, SellReturnRecord
from app.services.quant.runtime_parameters import get_paper_risk_control

MIN_CLOSED_TRADES = 100
MIN_SHARED_DAYS = 10


@dataclass(frozen=True)
class StrategyWeightDecision:
    strategy_key: str
    weight: float
    scale: Decimal
    trade_count: int
    max_correlation: float
    reason: str


class PaperStrategyPortfolioAllocator:
    """Use real paper closed-trade samples to derive Markowitz sizing scales."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.performance = PaperPerformanceService(db)

    def build_strategy_scales(self, *, account_id: int) -> dict[str, StrategyWeightDecision]:
        records = self.performance.sell_return_records(account_id)
        if len(records) < MIN_CLOSED_TRADES:
            return {}
        matrix, strategies, counts = _daily_return_matrix(records)
        if matrix.size == 0 or len(strategies) < 2:
            return {}
        covariance, shared = _pairwise_covariance(matrix)
        if _min_shared_days(shared) < MIN_SHARED_DAYS:
            return {}
        mean_returns = np.nanmean(matrix, axis=0)
        covariance = np.atleast_2d(covariance) + np.eye(len(strategies)) * 1e-8
        weights = _max_sharpe_weights(mean_returns, covariance)
        params = _risk_control_params()
        penalties = _correlation_penalties(
            strategies,
            shared,
            matrix,
            weights,
            threshold=_float_param(params, "correlation_penalty_threshold"),
        )
        max_weight = max(float(value) for value in weights) if len(weights) else 0.0
        if max_weight <= 0:
            return {}
        min_scale = Decimal(str(_float_param(params, "correlation_min_scale") / 100)).quantize(Decimal("0.0001"))

        decisions: dict[str, StrategyWeightDecision] = {}
        for index, strategy in enumerate(strategies):
            adjusted_weight = float(weights[index]) * penalties[index]
            normalized_scale = Decimal(str(adjusted_weight / max_weight if max_weight > 0 else 0.0))
            scale = min(Decimal("1.0"), max(min_scale, normalized_scale)).quantize(Decimal("0.0001"))
            max_corr = _max_pair_correlation(index, matrix, shared)
            decisions[strategy] = StrategyWeightDecision(
                strategy_key=strategy,
                weight=round(adjusted_weight, 6),
                scale=scale,
                trade_count=counts.get(strategy, 0),
                max_correlation=round(max_corr, 4),
                reason=_reason_for(strategy, scale=scale, weight=adjusted_weight, max_corr=max_corr),
            )
        return decisions


def _daily_return_matrix(records: list[SellReturnRecord]) -> tuple[np.ndarray, list[str], dict[str, int]]:
    grouped: dict[str, dict[Any, float]] = {}
    counts: dict[str, int] = {}
    all_days: set[Any] = set()
    for item in records:
        strategy = item.strategy_key or "未分类"
        day = item.trade_time.date()
        grouped.setdefault(strategy, {})
        grouped[strategy][day] = grouped[strategy].get(day, 0.0) + (float(item.return_pct) / 100.0)
        counts[strategy] = counts.get(strategy, 0) + 1
        all_days.add(day)
    strategies = sorted(strategy for strategy, count in counts.items() if count > 0)
    days = sorted(all_days)
    if not strategies or not days:
        return np.empty((0, 0)), [], {}
    matrix = np.array(
        [[grouped[strategy].get(day, float("nan")) for strategy in strategies] for day in days],
        dtype=float,
    )
    return matrix, strategies, counts


def _pairwise_covariance(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    count = matrix.shape[1]
    covariance = np.zeros((count, count), dtype=float)
    shared = np.zeros((count, count), dtype=int)
    for left in range(count):
        for right in range(left, count):
            mask = np.isfinite(matrix[:, left]) & np.isfinite(matrix[:, right])
            overlap = int(mask.sum())
            shared[left, right] = overlap
            shared[right, left] = overlap
            if overlap >= 2:
                value = float(np.cov(matrix[mask, left], matrix[mask, right], ddof=1)[0, 1])
            else:
                value = 0.0
            covariance[left, right] = value
            covariance[right, left] = value
    return covariance, shared


def _min_shared_days(shared: np.ndarray) -> int:
    values = [
        int(shared[left, right])
        for left in range(shared.shape[0])
        for right in range(left + 1, shared.shape[1])
    ]
    return min(values) if values else 0


def _max_sharpe_weights(mean_returns: np.ndarray, covariance: np.ndarray) -> np.ndarray:
    count = len(mean_returns)
    initial = np.repeat(1.0 / count, count)
    bounds = [(0.0, 1.0)] * count
    constraints = ({"type": "eq", "fun": lambda weights: np.sum(weights) - 1.0},)

    def objective(weights: np.ndarray) -> float:
        expected = float(weights @ mean_returns)
        variance = float(weights.T @ covariance @ weights)
        volatility = max(float(np.sqrt(max(variance, 0.0))), 1e-8)
        return -((expected - 0.0) / volatility)

    result = minimize(objective, initial, method="SLSQP", bounds=bounds, constraints=constraints)
    if not result.success:
        return initial
    weights = np.asarray(result.x, dtype=float)
    total = float(weights.sum())
    return weights / total if total > 0 else initial


def _correlation_penalties(
    strategies: list[str],
    shared: np.ndarray,
    matrix: np.ndarray,
    weights: np.ndarray,
    *,
    threshold: float,
) -> list[float]:
    penalties = [1.0] * len(strategies)
    for left in range(len(strategies)):
        for right in range(left + 1, len(strategies)):
            corr = _pair_correlation(left, right, matrix, shared)
            if corr <= threshold:
                continue
            penalized = left if float(weights[left]) <= float(weights[right]) else right
            penalties[penalized] *= 0.8
    return penalties


def _pair_correlation(left: int, right: int, matrix: np.ndarray, shared: np.ndarray) -> float:
    if int(shared[left, right]) < MIN_SHARED_DAYS:
        return 0.0
    mask = np.isfinite(matrix[:, left]) & np.isfinite(matrix[:, right])
    if int(mask.sum()) < 2:
        return 0.0
    return float(np.corrcoef(matrix[mask, left], matrix[mask, right])[0, 1])


def _max_pair_correlation(index: int, matrix: np.ndarray, shared: np.ndarray) -> float:
    values = [
        _pair_correlation(index, other, matrix, shared)
        for other in range(matrix.shape[1])
        if other != index
    ]
    return max(values) if values else 0.0


def _reason_for(strategy: str, *, scale: Decimal, weight: float, max_corr: float) -> str:
    corr_part = f"；与其他策略最高相关系数 {max_corr:.2f}" if max_corr > 0 else ""
    return f"{strategy} 组合层权重 {weight * 100:.1f}% ，仓位缩放 {float(scale) * 100:.1f}%{corr_part}"


def _risk_control_params() -> dict[str, object]:
    values = {**PAPER_RISK_CONTROL_DEFAULTS}
    values.update(get_paper_risk_control())
    return values


def _float_param(params: dict[str, object], key: str) -> float:
    fallback = PAPER_RISK_CONTROL_DEFAULTS[key]
    try:
        return float(params.get(key, fallback))
    except (TypeError, ValueError):
        return float(fallback)
