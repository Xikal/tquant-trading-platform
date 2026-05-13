from __future__ import annotations

from typing import Any


DEFAULT_TRAINING_PARAMS: dict[str, Any] = {
    "cv_folds": 5,
    "min_train_samples": 1000,
    "incremental_model_type": "xgboost",
    "incremental_promote": True,
    "incremental_warm_start": True,
    "promotion_max_p_value": 0.05,
    "xgb_n_estimators": 120,
    "xgb_max_depth": 3,
    "xgb_learning_rate": 0.05,
    "lgb_n_estimators": 120,
    "lgb_max_depth": 4,
    "lgb_learning_rate": 0.05,
    "xgboost": {
        "n_estimators": 120,
        "max_depth": 3,
        "learning_rate": 0.05,
        "subsample": 0.85,
        "colsample_bytree": 0.85,
    },
    "lightgbm": {
        "n_estimators": 120,
        "max_depth": 4,
        "learning_rate": 0.05,
        "subsample": 0.85,
        "colsample_bytree": 0.85,
    },
}
