from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FactorCombinationResult:
    weights: dict[str, float]
    method: str
    warning: str = ""


def ic_weighted_combination(metrics_by_factor: dict[str, dict]) -> FactorCombinationResult:
    raw: dict[str, float] = {}
    for key, metrics in metrics_by_factor.items():
        ic = float(metrics.get("ic_mean") or 0.0)
        corr = abs(float(metrics.get("max_existing_factor_corr") or 0.0))
        raw[key] = max(ic, 0.0) * max(0.0, 1.0 - corr)
    total = sum(raw.values())
    if total <= 0:
        count = max(len(metrics_by_factor), 1)
        return FactorCombinationResult(
            weights={key: round(1.0 / count, 4) for key in metrics_by_factor},
            method="equal_weight",
            warning="IC 权重不可用，已回退等权。",
        )
    return FactorCombinationResult(
        weights={key: round(value / total, 4) for key, value in raw.items()},
        method="ic_weighted_orthogonal_penalty",
    )


def pca_first_component_weights(correlation_matrix: list[list[float]], factor_keys: list[str]) -> dict[str, float]:
    if not factor_keys:
        return {}
    matrix = np.array(correlation_matrix, dtype=float)
    if matrix.shape != (len(factor_keys), len(factor_keys)):
        return {key: round(1.0 / len(factor_keys), 4) for key in factor_keys}
    values, vectors = np.linalg.eigh(matrix)
    component = np.abs(vectors[:, int(np.argmax(values))])
    total = float(component.sum()) or 1.0
    return {key: round(float(component[index] / total), 4) for index, key in enumerate(factor_keys)}
