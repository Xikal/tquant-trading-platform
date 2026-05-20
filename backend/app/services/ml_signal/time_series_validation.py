from __future__ import annotations

from typing import Any

import numpy as np


def chronological_samples(rows: list[Any]) -> list[Any]:
    """Return ML samples in event-time order so validation never sees the future."""

    return sorted(rows, key=_sample_sort_key)


def time_series_holdout_split(
    x_matrix: np.ndarray,
    labels: np.ndarray,
    *,
    validation_ratio: float,
    gap: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, int]]:
    sample_count = int(len(labels))
    validation_count = max(1, int(round(sample_count * float(validation_ratio))))
    validation_count = min(validation_count, max(sample_count - 1, 1))
    validation_start = sample_count - validation_count
    train_end = max(1, validation_start - max(int(gap), 0))
    if train_end < 2 and validation_start > 1:
        train_end = validation_start
    metadata = {
        "train_end_index": int(train_end),
        "validation_start_index": int(validation_start),
        "validation_count": int(sample_count - validation_start),
        "gap": int(max(validation_start - train_end, 0)),
    }
    return (
        x_matrix[:train_end],
        x_matrix[validation_start:],
        labels[:train_end],
        labels[validation_start:],
        metadata,
    )


def time_series_cv_metrics(
    *,
    estimator: Any,
    x_matrix: np.ndarray,
    labels: np.ndarray,
    folds: int,
    gap: int,
    probability_fn,
) -> dict[str, Any]:
    from sklearn.base import clone
    from sklearn.metrics import accuracy_score, roc_auc_score
    from sklearn.model_selection import TimeSeriesSplit

    sample_count = int(len(labels))
    fold_count = min(max(int(folds), 2), max(sample_count - 1, 2))
    if sample_count < fold_count + 2:
        return {
            "cv_fold_count": 0,
            "cv_splitter": "TimeSeriesSplit",
            "cv_skipped_reason": "时序样本不足，无法执行交叉验证。",
        }

    accuracies: list[float] = []
    aucs: list[float] = []
    skipped = 0
    effective_gap = min(max(int(gap), 0), max(sample_count // (fold_count + 1) - 1, 0))
    splitter = TimeSeriesSplit(n_splits=fold_count, gap=effective_gap)
    for train_index, valid_index in splitter.split(x_matrix):
        train_labels = labels[train_index]
        valid_labels = labels[valid_index]
        if len(set(train_labels.tolist())) < 2 or len(set(valid_labels.tolist())) < 1:
            skipped += 1
            continue
        fold_estimator = clone(estimator)
        fold_estimator.fit(x_matrix[train_index], train_labels)
        probabilities = probability_fn(fold_estimator, x_matrix[valid_index])
        predictions = (probabilities >= 0.5).astype(int)
        accuracies.append(float(accuracy_score(valid_labels, predictions)))
        if len(set(valid_labels.tolist())) >= 2:
            aucs.append(float(roc_auc_score(valid_labels, probabilities)))

    metrics: dict[str, Any] = {
        "cv_fold_count": int(len(accuracies)),
        "cv_requested_fold_count": int(fold_count),
        "cv_effective_fold_count": int(len(accuracies)),
        "cv_skipped_fold_count": int(skipped),
        "cv_splitter": "TimeSeriesSplit",
        "cv_gap_samples": int(effective_gap),
        "cv_accuracy_mean": round(float(np.mean(accuracies)), 4) if accuracies else 0.0,
        "cv_accuracy_std": round(float(np.std(accuracies)), 4) if accuracies else 0.0,
    }
    if aucs:
        metrics["cv_auc_mean"] = round(float(np.mean(aucs)), 4)
        metrics["cv_auc_std"] = round(float(np.std(aucs)), 4)
    else:
        metrics["cv_auc_missing_reason"] = "时序交叉验证折内标签类别不足，无法计算 AUC。"
    return metrics


def _sample_sort_key(row: Any) -> tuple[str, str, int]:
    trade_date = str(getattr(row, "trade_date", "") or "")
    created_at = getattr(row, "created_at", None)
    created_key = created_at.isoformat() if created_at is not None else ""
    row_id = int(getattr(row, "id", 0) or 0)
    return (trade_date, created_key, row_id)
