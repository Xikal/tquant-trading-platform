from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import numpy as np

from app.core.database import SessionLocal, init_db
from app.services.paper.exit_model_dataset import (
    EXIT_MODEL_FEATURE_COLUMNS,
    build_exit_model_dataset,
    build_exit_model_dataset_from_shadow,
    synthetic_exit_model_records,
)
from app.services.paper.exit_model_schema import EXIT_MODEL_FEATURE_VERSION, EXIT_MODEL_VERSION


def main() -> int:
    parser = argparse.ArgumentParser(description="Train paper exit Shadow model")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-type", choices=("lightgbm", "xgboost", "logistic"), default="lightgbm")
    args = parser.parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset = build_exit_model_dataset(synthetic_exit_model_records()) if args.smoke else _dataset_from_db()
    x_train, y_train = _matrix(dataset.train_rows)
    x_valid, y_valid = _matrix(dataset.validation_rows)
    estimator, model_type, fallback_reason = _fit_estimator(args.model_type, x_train, y_train)
    valid_prob = _predict_proba(estimator, x_valid) if len(x_valid) else np.asarray([], dtype=float)
    metrics = _metrics(y_valid, valid_prob)
    payload = {
        "estimator": estimator,
        "model_type": model_type,
        "model_version": EXIT_MODEL_VERSION,
        "feature_version": EXIT_MODEL_FEATURE_VERSION,
        "feature_names": list(EXIT_MODEL_FEATURE_COLUMNS),
        "fallback_reason": fallback_reason,
        "metadata": dataset.metadata,
    }
    model_path = output_dir / "exit_model.pkl"
    with model_path.open("wb") as file:
        pickle.dump(payload, file)
    config = {
        "model_type": model_type,
        "requested_model_type": args.model_type,
        "model_version": EXIT_MODEL_VERSION,
        "feature_version": EXIT_MODEL_FEATURE_VERSION,
        "feature_names": list(EXIT_MODEL_FEATURE_COLUMNS),
        "fallback_reason": fallback_reason,
        "smoke": bool(args.smoke),
    }
    (output_dir / "training_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {
        **dataset.metadata,
        **metrics,
        "model_path": str(model_path),
        "model_type": model_type,
        "fallback_reason": fallback_reason,
        "groups": _group_report(dataset.test_rows),
    }
    (output_dir / "evaluation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"model": str(model_path), "report": str(output_dir / "evaluation_report.json"), "metrics": report}, ensure_ascii=False, indent=2))
    return 0


def _dataset_from_db():
    init_db()
    with SessionLocal() as db:
        return build_exit_model_dataset_from_shadow(db)


def _matrix(rows):
    x_rows = [[float(row.get(name, 0.0) or 0.0) for name in EXIT_MODEL_FEATURE_COLUMNS] for row in rows]
    labels = [1 if row.get("pullback_risk") else 0 for row in rows]
    return np.asarray(x_rows, dtype=float), np.asarray(labels, dtype=int)


def _fit_estimator(model_type: str, x_train: np.ndarray, y_train: np.ndarray):
    if len(x_train) == 0:
        return _RuleEstimator(), "rule_fallback", "empty_dataset"
    if len(set(y_train.tolist())) < 2:
        return _RuleEstimator(), "rule_fallback", "single_class_dataset"
    try:
        if model_type == "lightgbm":
            from lightgbm import LGBMClassifier

            estimator = LGBMClassifier(n_estimators=60, max_depth=3, learning_rate=0.05, random_state=42, verbosity=-1)
        elif model_type == "xgboost":
            from xgboost import XGBClassifier

            estimator = XGBClassifier(n_estimators=60, max_depth=3, learning_rate=0.05, random_state=42, n_jobs=1, eval_metric="logloss")
        else:
            estimator = _logistic_estimator()
        estimator.fit(x_train, y_train)
        return estimator, model_type, ""
    except Exception as exc:
        estimator = _logistic_estimator()
        try:
            estimator.fit(x_train, y_train)
            return estimator, "logistic", f"{model_type}_unavailable:{exc.__class__.__name__}"
        except Exception:
            return _RuleEstimator(), "rule_fallback", f"training_failed:{exc.__class__.__name__}"


def _logistic_estimator():
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    return Pipeline([("scaler", StandardScaler()), ("model", LogisticRegression(max_iter=300, solver="liblinear", class_weight="balanced"))])


def _predict_proba(estimator, matrix: np.ndarray) -> np.ndarray:
    if len(matrix) == 0:
        return np.asarray([], dtype=float)
    if hasattr(estimator, "predict_proba"):
        return np.asarray(estimator.predict_proba(matrix)[:, -1], dtype=float)
    return np.asarray(estimator.predict(matrix), dtype=float)


def _metrics(labels: np.ndarray, probabilities: np.ndarray) -> dict:
    if len(labels) == 0:
        return {"validation_count": 0, "validation_accuracy": 0.0, "validation_positive_rate": 0.0}
    predictions = probabilities >= 0.5
    return {
        "validation_count": int(len(labels)),
        "validation_accuracy": round(float((predictions == labels).mean()), 4),
        "validation_positive_rate": round(float(labels.mean()), 4),
        "avg_pullback_risk": round(float(probabilities.mean()), 4) if len(probabilities) else 0.0,
    }


def _group_report(rows: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("strategy_key") or "unknown"), []).append(row)
    return {
        key: {
            "sample_count": len(items),
            "pullback_risk_rate": round(sum(1 for item in items if item.get("pullback_risk")) / max(len(items), 1), 4),
            "avg_next_return_pct": round(sum(float(item.get("next_return_pct", 0.0) or 0.0) for item in items) / max(len(items), 1), 4),
        }
        for key, items in grouped.items()
    }


class _RuleEstimator:
    def predict_proba(self, matrix):
        result = []
        for row in matrix:
            pnl = float(row[0]) if len(row) else 0.0
            pullback = float(row[2]) if len(row) > 2 else 0.0
            risk = min(max(0.15 + max(pnl, 0) * 0.05 + pullback * 0.18, 0.0), 1.0)
            result.append([1.0 - risk, risk])
        return np.asarray(result, dtype=float)


if __name__ == "__main__":
    raise SystemExit(main())
