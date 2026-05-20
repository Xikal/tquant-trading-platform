from __future__ import annotations

from typing import Any


DEFAULT_TRAINING_PARAMS: dict[str, Any] = {
    "cv_folds": 5,
    "time_series_cv_gap_samples": 20,
    "min_train_samples": 1000,
    "incremental_model_type": "xgboost",
    "incremental_promote": True,
    "incremental_warm_start": True,
    "promotion_max_p_value": 0.05,
    "promotion_min_bootstrap_ci_lower": 0.50,
    "promotion_max_auc_gap": 0.08,
    "promotion_max_top5_importance_share": 0.60,
    "promotion_max_single_importance_share": 0.30,
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
