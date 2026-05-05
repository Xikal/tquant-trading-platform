from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import product
from typing import Any

from app.services.backtest.engine import BacktestConfig, BacktestEngine, BacktestResult


@dataclass(frozen=True)
class OptimizationCandidate:
    params: dict[str, Any]
    score: float
    metrics: dict[str, Any]


class BacktestOptimizer:
    """Phase 4 controlled skeleton: bounded grid search over engine config only."""

    def __init__(self, engine: BacktestEngine) -> None:
        self.engine = engine

    def grid_search(
        self,
        base_config: BacktestConfig,
        *,
        param_grid: dict[str, list[Any]],
        max_runs: int = 20,
        score_key: str = "total_return_pct",
    ) -> list[OptimizationCandidate]:
        candidates: list[OptimizationCandidate] = []
        keys = list(param_grid)
        values = [param_grid[key] for key in keys]
        for index, combination in enumerate(product(*values)):
            if index >= max_runs:
                break
            params = dict(zip(keys, combination))
            result = self.engine.run(replace(base_config, **params))
            candidates.append(_candidate(params=params, result=result, score_key=score_key))
        return sorted(candidates, key=lambda item: item.score, reverse=True)


def _candidate(*, params: dict[str, Any], result: BacktestResult, score_key: str) -> OptimizationCandidate:
    raw_score = result.metrics.get(score_key, 0.0)
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        score = 0.0
    return OptimizationCandidate(params=params, score=score, metrics=result.metrics)
