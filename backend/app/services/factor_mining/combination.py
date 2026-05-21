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


def ridge_regression_combination(
    factor_returns: dict[str, list[float]],
    target_returns: list[float],
    *,
    alpha: float = 1.0,
) -> FactorCombinationResult:
    factor_keys = [key for key, values in factor_returns.items() if values]
    if not factor_keys or not target_returns:
        return FactorCombinationResult(weights={}, method="ridge_regression", warning="Ridge 输入为空。")
    row_count = min([len(target_returns), *[len(factor_returns[key]) for key in factor_keys]])
    if row_count < max(5, len(factor_keys) + 2):
        return FactorCombinationResult(
            weights={key: round(1.0 / len(factor_keys), 4) for key in factor_keys},
            method="equal_weight",
            warning="样本不足，Ridge 已回退等权。",
        )
    x = np.array([factor_returns[key][-row_count:] for key in factor_keys], dtype=float).T
    y = np.array(target_returns[-row_count:], dtype=float)
    mask = np.isfinite(y) & np.all(np.isfinite(x), axis=1)
    x = x[mask]
    y = y[mask]
    if len(y) < max(5, len(factor_keys) + 2):
        return FactorCombinationResult(
            weights={key: round(1.0 / len(factor_keys), 4) for key in factor_keys},
            method="equal_weight",
            warning="有效样本不足，Ridge 已回退等权。",
        )
    x_mean = x.mean(axis=0)
    x_std = x.std(axis=0, ddof=1)
    x_std[x_std <= 1e-12] = 1.0
    x_scaled = (x - x_mean) / x_std
    y_centered = y - y.mean()
    penalty = max(float(alpha), 1e-6) * np.eye(len(factor_keys))
    try:
        coef = np.linalg.solve(x_scaled.T @ x_scaled + penalty, x_scaled.T @ y_centered)
    except np.linalg.LinAlgError:
        coef = np.linalg.pinv(x_scaled.T @ x_scaled + penalty) @ x_scaled.T @ y_centered
    positive = np.maximum(coef, 0.0)
    total = float(positive.sum())
    if total <= 1e-12:
        return FactorCombinationResult(
            weights={key: round(1.0 / len(factor_keys), 4) for key in factor_keys},
            method="equal_weight",
            warning="Ridge 权重非正，已回退等权。",
        )
    return FactorCombinationResult(
        weights={key: round(float(positive[index] / total), 4) for index, key in enumerate(factor_keys)},
        method="ridge_regression",
    )
