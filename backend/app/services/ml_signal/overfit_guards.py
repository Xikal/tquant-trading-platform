from __future__ import annotations

from typing import Any

import numpy as np


def bootstrap_accuracy_ci(
    labels: np.ndarray,
    predictions: np.ndarray,
    *,
    rounds: int = 1000,
    confidence: float = 0.95,
) -> dict[str, float]:
    if len(labels) == 0:
        return {"lower": 0.0, "upper": 0.0}
    rng = np.random.default_rng(42)
    values: list[float] = []
    n = len(labels)
    for _ in range(max(100, int(rounds))):
        index = rng.integers(0, n, n)
        values.append(float((predictions[index] == labels[index]).mean()))
    alpha = max(0.0, min(1.0, 1.0 - confidence))
    return {
        "lower": round(float(np.quantile(values, alpha / 2)), 4),
        "upper": round(float(np.quantile(values, 1 - alpha / 2)), 4),
    }


def feature_importance_concentration(estimator: Any) -> dict[str, float]:
    values = _importance_values(estimator)
    if values is None or len(values) == 0 or float(np.sum(np.abs(values))) <= 0:
        return {}
    weights = np.abs(values).astype(float)
    weights = weights / float(weights.sum())
    ordered = np.sort(weights)[::-1]
    return {
        "feature_importance_top5_share": round(float(ordered[:5].sum()), 4),
        "feature_importance_max_share": round(float(ordered[0]), 4),
    }


def _importance_values(estimator: Any) -> np.ndarray | None:
    if hasattr(estimator, "feature_importances_"):
        return np.asarray(getattr(estimator, "feature_importances_"), dtype=float)
    if hasattr(estimator, "named_steps"):
        model = estimator.named_steps.get("model")
        if model is not None and hasattr(model, "coef_"):
            return np.ravel(np.asarray(model.coef_, dtype=float))
    if hasattr(estimator, "coef_"):
        return np.ravel(np.asarray(estimator.coef_, dtype=float))
    return None
