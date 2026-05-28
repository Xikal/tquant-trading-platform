from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import numpy as np

from app.core.config import get_settings
from app.models.entities import MLSignalModel
from app.models.schema_defs.phase4 import MLSignalModelOut, MLSignalTrainRequest
from app.services.ml_signal.features import estimator_probabilities as _estimator_probabilities
from app.services.ml_signal.overfit_guards import bootstrap_accuracy_ci, feature_importance_concentration
from app.services.ml_signal.promotion_quality import binomial_accuracy_p_value
from app.services.ml_signal.training_runtime import (
    configured_cv_folds,
    configured_cv_gap_samples,
    effective_min_train_samples,
    max_validation_p_value,
    model_training_params,
)
from app.services.ml_signal.time_series_validation import time_series_cv_metrics, time_series_holdout_split

def fit_estimator(
    *,
    model_type: str,
    x_matrix: np.ndarray,
    labels: np.ndarray,
    validation_ratio: float,
    warm_start_estimator: Any | None = None,
):
    from sklearn.metrics import accuracy_score, roc_auc_score

    gap = configured_cv_gap_samples()
    x_train, x_valid, y_train, y_valid, split_metadata = time_series_holdout_split(
        x_matrix,
        labels,
        validation_ratio=validation_ratio,
        gap=gap,
    )
    estimator = _make_estimator(model_type)
    cv_metrics = _cross_validate_estimator(
        estimator=estimator,
        x_matrix=x_matrix,
        labels=labels,
        folds=configured_cv_folds(),
        gap=gap,
    )
    _fit_with_optional_warm_start(estimator, x_train, y_train, warm_start_estimator)
    probabilities = _estimator_probabilities(estimator, x_valid)
    train_probabilities = _estimator_probabilities(estimator, x_train)
    predictions = (probabilities >= 0.5).astype(int)
    correct_count = int((predictions == y_valid).sum())
    metrics = {
        "sample_count": int(len(labels)),
        "train_count": int(len(y_train)),
        "validation_count": int(len(y_valid)),
        "validation_method": "time_series_holdout",
        "validation_gap_samples": int(split_metadata.get("gap", gap)),
        "scaler_fit_scope": "train_only",
        "temporal_order_enforced": True,
        "positive_rate": round(float(labels.mean()), 4),
        "validation_accuracy": round(float(accuracy_score(y_valid, predictions)), 4),
        "validation_correct_count": correct_count,
        "validation_accuracy_p_value": round(
            binomial_accuracy_p_value(correct_count, int(len(y_valid)), baseline=0.5),
            8,
        ),
        **cv_metrics,
    }
    ci = bootstrap_accuracy_ci(y_valid, predictions)
    metrics["validation_accuracy_ci95_lower"] = ci["lower"]
    metrics["validation_accuracy_ci95_upper"] = ci["upper"]
    if len(set(y_valid.tolist())) >= 2:
        metrics["validation_auc"] = round(float(roc_auc_score(y_valid, probabilities)), 4)
    if len(set(y_train.tolist())) >= 2 and "validation_auc" in metrics:
        train_auc = float(roc_auc_score(y_train, train_probabilities))
        metrics["train_auc"] = round(train_auc, 4)
        metrics["train_validation_auc_gap"] = round(train_auc - float(metrics["validation_auc"]), 4)
    metrics.update(feature_importance_concentration(estimator))
    return estimator, metrics


def _fit_with_optional_warm_start(estimator: Any, x_train: np.ndarray, y_train: np.ndarray, previous: Any | None) -> None:
    if previous is not None and estimator.__class__.__name__ == "XGBClassifier":
        booster = getattr(previous, "get_booster", lambda: None)()
        if booster is not None:
            estimator.fit(x_train, y_train, xgb_model=booster)
            return
    estimator.fit(x_train, y_train)


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

    params = model_training_params("logistic")
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    max_iter=_int_param(params, "max_iter", 500),
                    random_state=42,
                    solver="liblinear",
                    C=_float_param(params, "c", 0.2),
                    class_weight="balanced",
                ),
            ),
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


def _cross_validate_estimator(*, estimator: Any, x_matrix: np.ndarray, labels: np.ndarray, folds: int, gap: int) -> dict[str, Any]:
    class_counts = np.bincount(labels.astype(int))
    if len(class_counts) < 2 or int(class_counts.min()) < 2:
        return {
            "cv_fold_count": 0,
            "cv_splitter": "TimeSeriesSplit",
            "cv_skipped_reason": "样本类别分布不足，无法执行时序交叉验证。",
        }

    return time_series_cv_metrics(
        estimator=estimator,
        x_matrix=x_matrix,
        labels=labels,
        folds=folds,
        gap=gap,
        probability_fn=_estimator_probabilities,
    )


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
    max_p_value = float(getattr(payload, "max_validation_p_value", 0.05) or 0.05)
    global_params = training_parameters_safe()
    validation_accuracy = float(metrics.get("validation_accuracy", 0.0) or 0.0)
    validation_auc = metrics.get("validation_auc")
    cv_fold_count = int(metrics.get("cv_fold_count", 0) or 0)
    cv_accuracy = metrics.get("cv_accuracy_mean")
    cv_auc = metrics.get("cv_auc_mean")
    cv_accuracy_std = metrics.get("cv_accuracy_std")
    cv_auc_std = metrics.get("cv_auc_std")
    validation_p_value = metrics.get("validation_accuracy_p_value")
    ci_lower = metrics.get("validation_accuracy_ci95_lower")
    auc_gap = metrics.get("train_validation_auc_gap")
    top5_share = metrics.get("feature_importance_top5_share")
    max_share = metrics.get("feature_importance_max_share")

    if sample_count < min_samples:
        blocks.append(f"生产模型样本量不足：当前 {sample_count}，最低需要 {min_samples}")
    if validation_accuracy < min_accuracy:
        blocks.append(f"validation_accuracy {validation_accuracy:.3f} 低于生产阈值 {min_accuracy:.3f}")
    if validation_auc is None:
        blocks.append("validation_auc 缺失，不能晋级生产模型")
    elif float(validation_auc or 0.0) < min_auc:
        blocks.append(f"validation_auc {float(validation_auc):.3f} 低于生产阈值 {min_auc:.3f}")
    if validation_p_value is None:
        blocks.append("validation_accuracy_p_value 缺失，不能晋级生产模型")
    elif float(validation_p_value) > max_p_value:
        blocks.append(f"validation_accuracy_p_value {float(validation_p_value):.4f} 高于显著性阈值 {max_p_value:.4f}")
    min_ci = float(global_params.get("promotion_min_bootstrap_ci_lower", 0.50) or 0.50)
    if ci_lower is None:
        blocks.append("validation_accuracy_ci95_lower 缺失，不能晋级生产模型")
    elif float(ci_lower or 0.0) <= min_ci:
        blocks.append(f"bootstrap 95% 胜率下限 {float(ci_lower):.3f} 未高于 {min_ci:.3f}")
    max_gap = float(global_params.get("promotion_max_auc_gap", 0.08) or 0.08)
    if auc_gap is not None and float(auc_gap) > max_gap:
        blocks.append(f"训练/验证 AUC 差 {float(auc_gap):.3f} 高于过拟合阈值 {max_gap:.3f}")
    max_top5 = float(global_params.get("promotion_max_top5_importance_share", 0.60) or 0.60)
    max_single = float(global_params.get("promotion_max_single_importance_share", 0.30) or 0.30)
    if top5_share is not None and float(top5_share) > max_top5:
        blocks.append(f"Top-5 特征重要性占比 {float(top5_share):.3f} 高于阈值 {max_top5:.3f}")
    if max_share is not None and float(max_share) > max_single:
        blocks.append(f"单一特征重要性占比 {float(max_share):.3f} 高于阈值 {max_single:.3f}")
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


def training_parameters_safe() -> dict[str, Any]:
    from app.services.ml_signal.training_runtime import training_parameters

    try:
        return training_parameters()
    except Exception:
        return {}


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
    validation_p_value = metrics.get("validation_accuracy_p_value")
    ci_lower = metrics.get("validation_accuracy_ci95_lower")
    auc_gap = metrics.get("train_validation_auc_gap")
    top5_share = metrics.get("feature_importance_top5_share")
    max_share = metrics.get("feature_importance_max_share")
    if sample_count < effective_min_train_samples(0):
        return "production 模型样本量低于当前安全阈值，本次按研究信号处理。"
    if metrics.get("temporal_order_enforced") is not True:
        return "production 模型缺少时序验证防泄漏标记，本次按研究信号处理。"
    if not metrics.get("feature_schema_hash"):
        return "production 模型缺少特征签名，本次按研究信号处理。"
    if validation_accuracy < float(settings.ml_signal_min_production_accuracy):
        return "production 模型准确率低于当前安全阈值，本次按研究信号处理。"
    if validation_auc is None or float(validation_auc or 0.0) < float(settings.ml_signal_min_production_auc):
        return "production 模型 AUC 低于当前安全阈值，本次按研究信号处理。"
    if validation_p_value is None or float(validation_p_value) > max_validation_p_value():
        return "production 模型验证显著性不足，本次按研究信号处理。"
    params = training_parameters_safe()
    if ci_lower is None or float(ci_lower or 0.0) <= float(params.get("promotion_min_bootstrap_ci_lower", 0.50) or 0.50):
        return "production 模型 Bootstrap 置信下限不足，本次按研究信号处理。"
    if auc_gap is not None and float(auc_gap) > float(params.get("promotion_max_auc_gap", 0.08) or 0.08):
        return "production 模型训练/验证 AUC 差过大，本次按研究信号处理。"
    if top5_share is not None and float(top5_share) > float(params.get("promotion_max_top5_importance_share", 0.60) or 0.60):
        return "production 模型特征集中度过高，本次按研究信号处理。"
    if max_share is not None and float(max_share) > float(params.get("promotion_max_single_importance_share", 0.30) or 0.30):
        return "production 模型过度依赖单一特征，本次按研究信号处理。"
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
