from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.ml_signal.model_defaults import DEFAULT_TRAINING_PARAMS
from app.services.quant.parameter_version_service import QuantParameterVersionService
from app.services.quant.runtime_parameters import get_ml_signal_training


def training_parameters() -> dict[str, Any]:
    values = get_ml_signal_training()
    return deepcopy(values) if isinstance(values, dict) else deepcopy(DEFAULT_TRAINING_PARAMS)


def model_training_params(model_type: str) -> dict[str, Any]:
    values = training_parameters()
    nested = values.get(model_type, {})
    params = deepcopy(nested) if isinstance(nested, dict) else {}
    prefix = "xgb" if model_type == "xgboost" else "lgb" if model_type == "lightgbm" else ""
    if prefix:
        for key in ("n_estimators", "max_depth", "learning_rate", "subsample", "colsample_bytree"):
            alias = f"{prefix}_{key}"
            if alias in values:
                params[key] = values[alias]
    return params


def configured_cv_folds() -> int:
    fallback = int(get_settings().ml_signal_cv_folds)
    return _bounded_int(training_parameters().get("cv_folds"), fallback=fallback, minimum=2, maximum=20)


def configured_cv_gap_samples() -> int:
    return _bounded_int(
        training_parameters().get("time_series_cv_gap_samples"),
        fallback=20,
        minimum=0,
        maximum=500,
    )


def effective_min_train_samples(payload_min_samples: int) -> int:
    settings_min = int(get_settings().ml_signal_min_production_samples)
    configured_min = _bounded_int(
        training_parameters().get("min_train_samples"),
        fallback=settings_min,
        minimum=20,
        maximum=1_000_000,
    )
    return max(int(payload_min_samples), settings_min, configured_min)


def incremental_model_type() -> str:
    value = str(training_parameters().get("incremental_model_type") or "xgboost").strip().lower()
    return value if value in {"logistic", "xgboost", "lightgbm"} else "xgboost"


def incremental_promote_enabled() -> bool:
    return _bool_param(training_parameters().get("incremental_promote"), fallback=True)


def incremental_warm_start_enabled() -> bool:
    return _bool_param(training_parameters().get("incremental_warm_start"), fallback=True)


def max_validation_p_value() -> float:
    return _bounded_float(training_parameters().get("promotion_max_p_value"), fallback=0.05, minimum=0.001, maximum=1.0)


def training_parameter_snapshot(db: Session) -> dict[str, Any]:
    try:
        current = QuantParameterVersionService(db).current(scope="low_buy")
    except Exception:
        return {}
    return {
        "parameter_set_id": current.id,
        "parameter_version": current.version,
        "parameter_scope": current.scope,
    }


def _bounded_int(value: Any, *, fallback: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        parsed = fallback
    return max(minimum, min(parsed, maximum))


def _bounded_float(value: Any, *, fallback: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = fallback
    return max(minimum, min(parsed, maximum))


def _bool_param(value: Any, *, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if value is None:
        return fallback
    return bool(value)
