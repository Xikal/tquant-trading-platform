from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import numpy as np

from app.core.config import get_settings
from app.models.entities import MLSignalModel
from app.models.schema_defs.phase4 import MLSignalModelOut, MLSignalTrainRequest
from app.services.ml_signal.features import estimator_probabilities as _estimator_probabilities
from app.services.ml_signal.training_runtime import configured_cv_folds, effective_min_train_samples, model_training_params

def fit_estimator(*, model_type: str, x_matrix: np.ndarray, labels: np.ndarray, validation_ratio: float):
    from sklearn.metrics import accuracy_score, roc_auc_score
    from sklearn.model_selection import train_test_split

    stratify = labels if min(np.bincount(labels.astype(int))) >= 2 else None
    x_train, x_valid, y_train, y_valid = train_test_split(
        x_matrix,
        labels,
        test_size=validation_ratio,
        random_state=42,
        stratify=stratify,
    )
    estimator = _make_estimator(model_type)
    cv_metrics = _cross_validate_estimator(
        estimator=estimator,
        x_matrix=x_matrix,
        labels=labels,
        folds=configured_cv_folds(),
    )
    estimator.fit(x_train, y_train)
    probabilities = _estimator_probabilities(estimator, x_valid)
    predictions = (probabilities >= 0.5).astype(int)
    metrics = {
        "sample_count": int(len(labels)),
        "train_count": int(len(y_train)),
        "validation_count": int(len(y_valid)),
        "positive_rate": round(float(labels.mean()), 4),
        "validation_accuracy": round(float(accuracy_score(y_valid, predictions)), 4),
        **cv_metrics,
    }
    if len(set(y_valid.tolist())) >= 2:
        metrics["validation_auc"] = round(float(roc_auc_score(y_valid, probabilities)), 4)
    return estimator, metrics


def _make_estimator(model_type: str):
    if model_type == "xgboost":
        from xgboost import XGBClassifier

        params = model_training_params("xgboost")
        return XGBClassifier(
            n_estimators=_int_param(params, "n_estimators", 120),
            max_depth=_int_param(params, "max_depth", 3),
            learning_rate=_float_param(params, "learning_rate", 0.05),
            subsample=_float_param(params, "subsample", 0.85),
            colsample_bytree=_float_param(params, "colsample_bytree", 0.85),
            eval_metric="logloss",
            n_jobs=1,
            random_state=42,
        )
    if model_type == "lightgbm":
        from lightgbm import LGBMClassifier

        params = model_training_params("lightgbm")
        return LGBMClassifier(
            n_estimators=_int_param(params, "n_estimators", 120),
            max_depth=_int_param(params, "max_depth", 4),
            learning_rate=_float_param(params, "learning_rate", 0.05),
            subsample=_float_param(params, "subsample", 0.85),
            colsample_bytree=_float_param(params, "colsample_bytree", 0.85),
            random_state=42,
            verbosity=-1,
        )
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    return Pipeline(
        [
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(max_iter=500, random_state=42)),
        ]
    )


def _int_param(params: dict[str, Any], key: str, fallback: int) -> int:
    try:
        return int(params.get(key, fallback))
    except (TypeError, ValueError):
        return fallback


def _float_param(params: dict[str, Any], key: str, fallback: float) -> float:
    try:
        return float(params.get(key, fallback))
    except (TypeError, ValueError):
        return fallback


def _cross_validate_estimator(*, estimator: Any, x_matrix: np.ndarray, labels: np.ndarray, folds: int) -> dict[str, Any]:
    from sklearn.base import clone
    from sklearn.metrics import accuracy_score, roc_auc_score
    from sklearn.model_selection import StratifiedKFold

    class_counts = np.bincount(labels.astype(int))
    min_class_count = int(class_counts.min()) if len(class_counts) >= 2 else 0
    fold_count = min(max(int(folds), 2), min_class_count)
    if fold_count < 2:
        return {
            "cv_fold_count": 0,
            "cv_skipped_reason": "样本类别分布不足，无法执行分层交叉验证。",
        }

    accuracies: list[float] = []
    aucs: list[float] = []
    splitter = StratifiedKFold(n_splits=fold_count, shuffle=True, random_state=42)
    for train_index, valid_index in splitter.split(x_matrix, labels):
        fold_estimator = clone(estimator)
        fold_estimator.fit(x_matrix[train_index], labels[train_index])
        probabilities = _estimator_probabilities(fold_estimator, x_matrix[valid_index])
        predictions = (probabilities >= 0.5).astype(int)
        valid_labels = labels[valid_index]
        accuracies.append(float(accuracy_score(valid_labels, predictions)))
        if len(set(valid_labels.tolist())) >= 2:
            aucs.append(float(roc_auc_score(valid_labels, probabilities)))

    metrics: dict[str, Any] = {
        "cv_fold_count": fold_count,
        "cv_accuracy_mean": round(float(np.mean(accuracies)), 4) if accuracies else 0.0,
        "cv_accuracy_std": round(float(np.std(accuracies)), 4) if accuracies else 0.0,
    }
    if aucs:
        metrics["cv_auc_mean"] = round(float(np.mean(aucs)), 4)
        metrics["cv_auc_std"] = round(float(np.std(aucs)), 4)
    else:
        metrics["cv_auc_missing_reason"] = "交叉验证折内标签类别不足，无法计算 AUC。"
    return metrics


def promotion_blocks(*, payload: MLSignalTrainRequest, metrics: dict[str, Any], sample_count: int) -> list[str]:
    settings = get_settings()
    blocks: list[str] = []
    min_samples = effective_min_train_samples(payload.min_samples)
    min_accuracy = max(float(settings.ml_signal_min_production_accuracy), float(payload.min_validation_accuracy))
    min_auc = float(settings.ml_signal_min_production_auc)
    min_cv_accuracy = float(settings.ml_signal_min_cv_accuracy)
    min_cv_auc = float(settings.ml_signal_min_cv_auc)
    max_cv_accuracy_std = float(settings.ml_signal_max_cv_accuracy_std)
    max_cv_auc_std = float(settings.ml_signal_max_cv_auc_std)
    validation_accuracy = float(metrics.get("validation_accuracy", 0.0) or 0.0)
    validation_auc = metrics.get("validation_auc")
    cv_fold_count = int(metrics.get("cv_fold_count", 0) or 0)
    cv_accuracy = metrics.get("cv_accuracy_mean")
    cv_auc = metrics.get("cv_auc_mean")
    cv_accuracy_std = metrics.get("cv_accuracy_std")
    cv_auc_std = metrics.get("cv_auc_std")

    if sample_count < min_samples:
        blocks.append(f"生产模型样本量不足：当前 {sample_count}，最低需要 {min_samples}")
    if validation_accuracy < min_accuracy:
        blocks.append(f"validation_accuracy {validation_accuracy:.3f} 低于生产阈值 {min_accuracy:.3f}")
    if validation_auc is None:
        blocks.append("validation_auc 缺失，不能晋级生产模型")
    elif float(validation_auc or 0.0) < min_auc:
        blocks.append(f"validation_auc {float(validation_auc):.3f} 低于生产阈值 {min_auc:.3f}")
    if cv_fold_count < 2:
        blocks.append("交叉验证未完成，不能晋级生产模型")
    if cv_accuracy is None:
        blocks.append("cv_accuracy_mean 缺失，不能晋级生产模型")
    elif float(cv_accuracy or 0.0) < min_cv_accuracy:
        blocks.append(f"cv_accuracy_mean {float(cv_accuracy):.3f} 低于生产阈值 {min_cv_accuracy:.3f}")
    if cv_accuracy_std is None:
        blocks.append("cv_accuracy_std 缺失，不能晋级生产模型")
    elif float(cv_accuracy_std or 0.0) > max_cv_accuracy_std:
        blocks.append(f"cv_accuracy_std {float(cv_accuracy_std):.3f} 高于稳定性阈值 {max_cv_accuracy_std:.3f}")
    if cv_auc is None:
        blocks.append("cv_auc_mean 缺失，不能晋级生产模型")
    elif float(cv_auc or 0.0) < min_cv_auc:
        blocks.append(f"cv_auc_mean {float(cv_auc):.3f} 低于生产阈值 {min_cv_auc:.3f}")
    if cv_auc_std is None:
        blocks.append("cv_auc_std 缺失，不能晋级生产模型")
    elif float(cv_auc_std or 0.0) > max_cv_auc_std:
        blocks.append(f"cv_auc_std {float(cv_auc_std):.3f} 高于稳定性阈值 {max_cv_auc_std:.3f}")
    return blocks


def production_model_warning(status: str, metrics: dict[str, Any]) -> str:
    if status != "production":
        return "模型未进入 production，仅用于研究和观察。"
    settings = get_settings()
    sample_count = int(metrics.get("sample_count", 0) or 0)
    validation_accuracy = float(metrics.get("validation_accuracy", 0.0) or 0.0)
    validation_auc = metrics.get("validation_auc")
    cv_fold_count = int(metrics.get("cv_fold_count", 0) or 0)
    cv_accuracy = metrics.get("cv_accuracy_mean")
    cv_auc = metrics.get("cv_auc_mean")
    cv_accuracy_std = metrics.get("cv_accuracy_std")
    cv_auc_std = metrics.get("cv_auc_std")
    if sample_count < effective_min_train_samples(0):
        return "production 模型样本量低于当前安全阈值，本次按研究信号处理。"
    if validation_accuracy < float(settings.ml_signal_min_production_accuracy):
        return "production 模型准确率低于当前安全阈值，本次按研究信号处理。"
    if validation_auc is None or float(validation_auc or 0.0) < float(settings.ml_signal_min_production_auc):
        return "production 模型 AUC 低于当前安全阈值，本次按研究信号处理。"
    if cv_fold_count < 2:
        return "production 模型缺少交叉验证，本次按研究信号处理。"
    if cv_accuracy is None or float(cv_accuracy or 0.0) < float(settings.ml_signal_min_cv_accuracy):
        return "production 模型交叉验证准确率低于当前安全阈值，本次按研究信号处理。"
    if cv_accuracy_std is None or float(cv_accuracy_std or 0.0) > float(settings.ml_signal_max_cv_accuracy_std):
        return "production 模型交叉验证稳定性不足，本次按研究信号处理。"
    if cv_auc is None or float(cv_auc or 0.0) < float(settings.ml_signal_min_cv_auc):
        return "production 模型交叉验证 AUC 低于当前安全阈值，本次按研究信号处理。"
    if cv_auc_std is None or float(cv_auc_std or 0.0) > float(settings.ml_signal_max_cv_auc_std):
        return "production 模型交叉验证 AUC 波动过大，本次按研究信号处理。"
    return ""


def model_out(row: MLSignalModel) -> MLSignalModelOut:
    schema = json_dict(row.feature_schema_json)
    metrics = json_dict(row.metrics_json)
    return MLSignalModelOut(
        model_key=row.model_key,
        model_type=row.model_type,
        status=model_effective_status(row),
        feature_names=list(schema.get("feature_names") or []),
        metrics=metrics,
        artifact_uri=row.artifact_uri,
        remote_artifact_uri=row.remote_artifact_uri,
        artifact_checksum=row.artifact_checksum,
        created_at=row.created_at,
    )


def model_effective_status(row: MLSignalModel) -> str:
    metrics = json_dict(row.metrics_json)
    if row.status != "production":
        return row.status
    if not row.artifact_uri or not (row.artifact_checksum or metrics.get("artifact_sha256")):
        return "research"
    return "research" if production_model_warning("production", metrics) else "production"


def generated_model_key(model_type: str) -> str:
    return f"{model_type}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def json_dict(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}
