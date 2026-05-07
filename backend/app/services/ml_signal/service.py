from __future__ import annotations

import json
import pickle
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import BACKEND_DIR, get_settings
from app.models.entities import BacktestTrade, MLSignalModel, MLSignalSample, PaperTrade
from app.models.schema_defs.phase4 import (
    MLSignalModelListResponse,
    MLSignalModelOut,
    MLSignalPredictionRequest,
    MLSignalPredictionResponse,
    MLSignalSampleBuildRequest,
    MLSignalSampleBuildResponse,
    MLSignalTrainRequest,
    MLSignalTrainResponse,
)


FEATURE_NAMES = [
    "price",
    "quantity",
    "gross_amount",
    "strategy_known",
    "market_state_known",
    "is_sell",
    "priority_score",
    "risk_score",
    "volume_shrink_ratio",
]

HEURISTIC_MODEL_KEY = "research-heuristic-v1"


class MLSignalService:
    """ML signal model service with research and production boundaries.

    The service can train/register models and serve promoted production models,
    but it remains an advisory signal surface. Trading permission, T+1, sizing
    and stop rules must still be enforced by deterministic backend risk logic.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def build_samples(self, payload: MLSignalSampleBuildRequest) -> MLSignalSampleBuildResponse:
        samples: list[dict[str, Any]] = []
        if payload.source in ("paper", "combined"):
            samples.extend(self._paper_samples(payload.limit))
        if payload.source in ("backtest", "combined") and len(samples) < payload.limit:
            samples.extend(self._backtest_samples(payload.limit - len(samples)))
        persisted = 0
        if payload.persist:
            for sample in samples:
                if self._persist_sample(sample):
                    persisted += 1
            self.db.commit()
        warning = ""
        if len(samples) < 1000:
            warning = "样本量不足，模型只能用于研究或小流量验证，不能单独决定交易动作。"
        return MLSignalSampleBuildResponse(
            source=payload.source,
            generated=len(samples),
            persisted=persisted,
            feature_names=FEATURE_NAMES,
            warning=warning,
        )

    def train(self, payload: MLSignalTrainRequest) -> MLSignalTrainResponse:
        rows = self._load_training_samples(source=payload.source, limit=payload.limit)
        if len(rows) < payload.min_samples:
            return MLSignalTrainResponse(
                model_key=payload.model_key or _generated_model_key(payload.model_type),
                model_type=payload.model_type,
                status="failed",
                sample_count=len(rows),
                feature_names=FEATURE_NAMES,
                warning=f"样本量不足：当前 {len(rows)}，最低需要 {payload.min_samples}。",
            )
        x_matrix, labels = _samples_to_matrix(rows)
        if len(set(labels.tolist())) < 2:
            return MLSignalTrainResponse(
                model_key=payload.model_key or _generated_model_key(payload.model_type),
                model_type=payload.model_type,
                status="failed",
                sample_count=len(rows),
                feature_names=FEATURE_NAMES,
                warning="训练样本标签只有单一类别，无法训练可用分类模型。",
            )

        model_key = payload.model_key or _generated_model_key(payload.model_type)
        try:
            estimator, metrics = _fit_estimator(
                model_type=payload.model_type,
                x_matrix=x_matrix,
                labels=labels,
                validation_ratio=payload.validation_ratio,
            )
        except Exception as exc:
            return MLSignalTrainResponse(
                model_key=model_key,
                model_type=payload.model_type,
                status="failed",
                sample_count=len(rows),
                feature_names=FEATURE_NAMES,
                warning=f"模型训练失败：{exc}",
            )
        promotion_blocks = _promotion_blocks(payload=payload, metrics=metrics, sample_count=len(rows))
        can_promote = payload.promote and not promotion_blocks
        status = "production" if can_promote else "research"
        if payload.promote and promotion_blocks:
            metrics["promotion_blocked_reason"] = "；".join(promotion_blocks)
        artifact_uri, artifact_sha256 = self._save_artifact(
            model_key=model_key,
            payload={
                "model_key": model_key,
                "model_type": payload.model_type,
                "feature_names": FEATURE_NAMES,
                "estimator": estimator,
                "metrics": metrics,
                "created_at": datetime.utcnow().isoformat(),
            },
        )
        metrics["artifact_sha256"] = artifact_sha256
        if status == "production":
            self.db.execute(
                MLSignalModel.__table__.update()
                .where(MLSignalModel.status == "production")
                .values(status="archived")
            )
        row = self.db.execute(select(MLSignalModel).where(MLSignalModel.model_key == model_key)).scalar_one_or_none()
        if row is None:
            row = MLSignalModel(model_key=model_key)
            self.db.add(row)
        row.model_type = payload.model_type
        row.status = status
        row.feature_schema_json = _json_dumps({"feature_names": FEATURE_NAMES})
        row.metrics_json = _json_dumps(metrics)
        row.artifact_uri = artifact_uri
        self.db.commit()
        self.db.refresh(row)

        return MLSignalTrainResponse(
            model_key=row.model_key,
            model_type=row.model_type,
            status=row.status,  # type: ignore[arg-type]
            sample_count=int(metrics.get("sample_count", len(rows))),
            feature_names=FEATURE_NAMES,
            metrics=metrics,
            artifact_uri=row.artifact_uri,
            warning="" if status == "production" else "模型已训练但未进入 production，当前仍按研究模型使用。",
        )

    def list_models(self, limit: int = 50) -> MLSignalModelListResponse:
        rows = self.db.execute(
            select(MLSignalModel).order_by(MLSignalModel.id.desc()).limit(max(1, min(limit, 200)))
        ).scalars().all()
        production = next((row.model_key for row in rows if _model_effective_status(row) == "production"), "")
        if not production:
            production_rows = self.db.execute(
                select(MLSignalModel)
                .where(MLSignalModel.status == "production")
                .order_by(MLSignalModel.id.desc())
                .limit(20)
            ).scalars().all()
            production = next((row.model_key for row in production_rows if _model_effective_status(row) == "production"), "")
        return MLSignalModelListResponse(
            items=[_model_out(row) for row in rows],
            production_model_key=production,
        )

    def predict(self, payload: MLSignalPredictionRequest) -> MLSignalPredictionResponse:
        row = self._select_model(payload.model_key)
        if row is not None and row.artifact_uri:
            try:
                metrics = _json_dict(row.metrics_json)
                artifact = self._load_artifact(
                    row.artifact_uri,
                    expected_sha256=str(metrics.get("artifact_sha256") or ""),
                )
                probability = _predict_probability(artifact["estimator"], payload.features)
                label = _label(probability)
                quality_warning = _production_model_warning(row.status, metrics)
                research_only = row.status != "production" or bool(quality_warning)
                return MLSignalPredictionResponse(
                    symbol=payload.symbol,
                    model_key=row.model_key,
                    model_type=row.model_type,
                    research_only=research_only,
                    probability=probability,
                    label=label,  # type: ignore[arg-type]
                    confidence=round(abs(probability - 0.5) * 2, 3),
                    reasons=[
                        f"使用 {row.status} 模型 {row.model_key} 推理。",
                        "输出仅作为信号因子，执行仍需后端风控确认。",
                    ],
                    metrics=metrics,
                    warning=quality_warning or ("" if row.status == "production" else "模型未进入 production，仅用于研究和观察。"),
                )
            except Exception as exc:
                return self._heuristic_predict(payload, warning=f"模型加载或推理失败，已降级启发式：{exc}")
        return self._heuristic_predict(payload)

    def _heuristic_predict(self, payload: MLSignalPredictionRequest, warning: str = "") -> MLSignalPredictionResponse:
        features = payload.features or {}
        score = 0.5
        reasons: list[str] = []
        if _to_float(features.get("priority_score")) >= 80:
            score += 0.18
            reasons.append("优先级分数较高。")
        if _to_float(features.get("risk_score")) >= 6:
            score -= 0.2
            reasons.append("风险分偏高。")
        if _to_float(features.get("volume_shrink_ratio")) and _to_float(features.get("volume_shrink_ratio")) <= 0.8:
            score += 0.08
            reasons.append("缩量承接特征较好。")
        probability = round(min(max(score, 0.0), 1.0), 3)
        return MLSignalPredictionResponse(
            symbol=payload.symbol,
            model_key=payload.model_key or HEURISTIC_MODEL_KEY,
            model_type="heuristic",
            research_only=True,
            probability=probability,
            label=_label(probability),  # type: ignore[arg-type]
            confidence=round(abs(probability - 0.5) * 2, 3),
            reasons=reasons or ["未找到 production 模型，输出启发式研究结果。"],
            warning=warning or "研究模型输出，不进入生产交易建议。",
        )

    def _select_model(self, model_key: str | None) -> MLSignalModel | None:
        cleaned = (model_key or "").strip()
        if cleaned and cleaned != HEURISTIC_MODEL_KEY:
            return self.db.execute(select(MLSignalModel).where(MLSignalModel.model_key == cleaned)).scalar_one_or_none()
        rows = self.db.execute(
            select(MLSignalModel)
            .where(MLSignalModel.status == "production")
            .order_by(MLSignalModel.id.desc())
            .limit(20)
        ).scalars().all()
        return next((row for row in rows if _model_effective_status(row) == "production"), None)

    def _load_training_samples(self, *, source: str, limit: int) -> list[MLSignalSample]:
        statement = select(MLSignalSample)
        if source in {"paper", "backtest"}:
            statement = statement.where(MLSignalSample.source == source)
        return self.db.execute(statement.order_by(MLSignalSample.id.desc()).limit(limit)).scalars().all()

    def _artifact_dir(self) -> Path:
        configured = Path(get_settings().ml_signal_model_dir)
        base = configured if configured.is_absolute() else BACKEND_DIR / configured
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _save_artifact(self, *, model_key: str, payload: dict[str, Any]) -> tuple[str, str]:
        path = self._artifact_dir() / f"{_safe_artifact_name(model_key)}.pkl"
        with path.open("wb") as file:
            pickle.dump(payload, file)
        return str(path), _file_sha256(path)

    def _load_artifact(self, artifact_uri: str, *, expected_sha256: str = "") -> dict[str, Any]:
        path = _validated_artifact_path(artifact_uri, self._artifact_dir())
        if not expected_sha256:
            raise ValueError("model artifact hash is missing")
        actual_sha256 = _file_sha256(path)
        if actual_sha256 != expected_sha256:
            raise ValueError("model artifact hash mismatch")
        with path.open("rb") as file:
            payload = pickle.load(file)
        if not isinstance(payload, dict) or "estimator" not in payload:
            raise ValueError("invalid model artifact")
        return payload

    def _paper_samples(self, limit: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(PaperTrade).order_by(PaperTrade.id.desc()).limit(limit)
        ).scalars().all()
        return [
            {
                "sample_key": f"paper:{row.id}",
                "symbol": row.symbol,
                "trade_date": row.trade_time.date().isoformat() if row.trade_time else "",
                "strategy_key": row.strategy_key,
                "source": "paper",
                "features": _trade_features(
                    price=float(row.price or 0),
                    quantity=int(row.quantity or 0),
                    gross_amount=float(row.gross_amount or 0),
                    strategy_key=row.strategy_key,
                    market_state=row.market_state,
                    side=row.side,
                ),
                "label": {"side": row.side, "net_amount": float(row.net_amount or 0)},
            }
            for row in rows
        ]

    def _backtest_samples(self, limit: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(BacktestTrade).order_by(BacktestTrade.id.desc()).limit(limit)
        ).scalars().all()
        return [
            {
                "sample_key": f"backtest:{row.id}",
                "symbol": row.symbol,
                "trade_date": row.trade_date,
                "strategy_key": row.strategy_key,
                "source": "backtest",
                "features": _trade_features(
                    price=float(row.price or 0),
                    quantity=int(row.quantity or 0),
                    gross_amount=float(row.gross_amount or 0),
                    strategy_key=row.strategy_key,
                    market_state=row.market_state,
                    side=row.side,
                ),
                "label": {"pnl_pct": float(row.pnl_pct or 0), "pnl_amount": float(row.pnl_amount or 0)},
            }
            for row in rows
        ]

    def _persist_sample(self, sample: dict[str, Any]) -> bool:
        existing = self.db.execute(
            select(MLSignalSample).where(MLSignalSample.sample_key == sample["sample_key"])
        ).scalar_one_or_none()
        if existing is not None:
            return False
        self.db.add(
            MLSignalSample(
                sample_key=sample["sample_key"],
                symbol=sample["symbol"],
                trade_date=sample["trade_date"],
                strategy_key=sample["strategy_key"],
                source=sample["source"],
                feature_json=_json_dumps(sample["features"]),
                label_json=_json_dumps(sample["label"]),
            )
        )
        return True


def _fit_estimator(*, model_type: str, x_matrix: np.ndarray, labels: np.ndarray, validation_ratio: float):
    from sklearn.metrics import accuracy_score, roc_auc_score
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression

    stratify = labels if min(np.bincount(labels.astype(int))) >= 2 else None
    x_train, x_valid, y_train, y_valid = train_test_split(
        x_matrix,
        labels,
        test_size=validation_ratio,
        random_state=42,
        stratify=stratify,
    )
    if model_type == "xgboost":
        from xgboost import XGBClassifier

        estimator = XGBClassifier(
            n_estimators=120,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.85,
            colsample_bytree=0.85,
            eval_metric="logloss",
            n_jobs=1,
            random_state=42,
        )
    elif model_type == "lightgbm":
        from lightgbm import LGBMClassifier

        estimator = LGBMClassifier(
            n_estimators=120,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=42,
            verbosity=-1,
        )
    else:
        estimator = Pipeline(
            [
                ("scaler", StandardScaler()),
                ("model", LogisticRegression(max_iter=500, random_state=42)),
            ]
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
    }
    if len(set(y_valid.tolist())) >= 2:
        metrics["validation_auc"] = round(float(roc_auc_score(y_valid, probabilities)), 4)
    return estimator, metrics


def _promotion_blocks(*, payload: MLSignalTrainRequest, metrics: dict[str, Any], sample_count: int) -> list[str]:
    settings = get_settings()
    blocks: list[str] = []
    min_samples = max(int(settings.ml_signal_min_production_samples), int(payload.min_samples))
    min_accuracy = max(float(settings.ml_signal_min_production_accuracy), float(payload.min_validation_accuracy))
    min_auc = float(settings.ml_signal_min_production_auc)
    validation_accuracy = float(metrics.get("validation_accuracy", 0.0) or 0.0)
    validation_auc = metrics.get("validation_auc")

    if sample_count < min_samples:
        blocks.append(f"生产模型样本量不足：当前 {sample_count}，最低需要 {min_samples}")
    if validation_accuracy < min_accuracy:
        blocks.append(f"validation_accuracy {validation_accuracy:.3f} 低于生产阈值 {min_accuracy:.3f}")
    if validation_auc is None:
        blocks.append("validation_auc 缺失，不能晋级生产模型")
    elif float(validation_auc or 0.0) < min_auc:
        blocks.append(f"validation_auc {float(validation_auc):.3f} 低于生产阈值 {min_auc:.3f}")
    return blocks


def _production_model_warning(status: str, metrics: dict[str, Any]) -> str:
    if status != "production":
        return "模型未进入 production，仅用于研究和观察。"
    settings = get_settings()
    sample_count = int(metrics.get("sample_count", 0) or 0)
    validation_accuracy = float(metrics.get("validation_accuracy", 0.0) or 0.0)
    validation_auc = metrics.get("validation_auc")
    if sample_count < int(settings.ml_signal_min_production_samples):
        return "production 模型样本量低于当前安全阈值，本次按研究信号处理。"
    if validation_accuracy < float(settings.ml_signal_min_production_accuracy):
        return "production 模型准确率低于当前安全阈值，本次按研究信号处理。"
    if validation_auc is None or float(validation_auc or 0.0) < float(settings.ml_signal_min_production_auc):
        return "production 模型 AUC 低于当前安全阈值，本次按研究信号处理。"
    return ""


def _samples_to_matrix(rows: list[MLSignalSample]) -> tuple[np.ndarray, np.ndarray]:
    x_rows: list[list[float]] = []
    labels: list[int] = []
    for row in rows:
        features = _json_dict(row.feature_json)
        label = _json_dict(row.label_json)
        x_rows.append([_to_float(features.get(name)) for name in FEATURE_NAMES])
        labels.append(1 if _label_is_positive(label) else 0)
    return np.asarray(x_rows, dtype=float), np.asarray(labels, dtype=int)


def _predict_probability(estimator: Any, features: dict[str, Any]) -> float:
    x_matrix = np.asarray([[_to_float(features.get(name)) for name in FEATURE_NAMES]], dtype=float)
    probability = float(_estimator_probabilities(estimator, x_matrix)[0])
    return round(min(max(probability, 0.0), 1.0), 3)


def _estimator_probabilities(estimator: Any, x_matrix: np.ndarray) -> np.ndarray:
    if hasattr(estimator, "predict_proba"):
        values = estimator.predict_proba(x_matrix)
        return np.asarray(values[:, 1], dtype=float)
    values = estimator.predict(x_matrix)
    return np.asarray(values, dtype=float)


def _trade_features(
    *,
    price: float,
    quantity: int,
    gross_amount: float,
    strategy_key: str,
    market_state: str,
    side: str,
) -> dict[str, Any]:
    return {
        "price": price,
        "quantity": quantity,
        "gross_amount": gross_amount,
        "strategy_known": 1 if strategy_key else 0,
        "market_state_known": 1 if market_state else 0,
        "is_sell": 1 if side == "sell" else 0,
        "priority_score": 0.0,
        "risk_score": 0.0,
        "volume_shrink_ratio": 0.0,
    }


def _label_is_positive(label: dict[str, Any]) -> bool:
    if "pnl_pct" in label:
        return _to_float(label.get("pnl_pct")) > 0
    if "pnl_amount" in label:
        return _to_float(label.get("pnl_amount")) > 0
    return _to_float(label.get("net_amount")) > 0


def _model_out(row: MLSignalModel) -> MLSignalModelOut:
    schema = _json_dict(row.feature_schema_json)
    metrics = _json_dict(row.metrics_json)
    return MLSignalModelOut(
        model_key=row.model_key,
        model_type=row.model_type,
        status=_model_effective_status(row),
        feature_names=list(schema.get("feature_names") or []),
        metrics=metrics,
        artifact_uri=row.artifact_uri,
        created_at=row.created_at,
    )


def _model_effective_status(row: MLSignalModel) -> str:
    metrics = _json_dict(row.metrics_json)
    if row.status != "production":
        return row.status
    if not row.artifact_uri or not metrics.get("artifact_sha256"):
        return "research"
    return "research" if _production_model_warning("production", metrics) else "production"


def _label(probability: float) -> str:
    if probability >= 0.62:
        return "positive"
    if probability <= 0.38:
        return "negative"
    return "neutral"


def _generated_model_key(model_type: str) -> str:
    return f"{model_type}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"


def _safe_artifact_name(model_key: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in model_key)[:120]


def _validated_artifact_path(artifact_uri: str, artifact_dir: Path) -> Path:
    base = artifact_dir.resolve()
    path = Path(artifact_uri).expanduser()
    resolved = path.resolve()
    if resolved.suffix != ".pkl":
        raise ValueError("invalid model artifact suffix")
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise ValueError("model artifact path escapes configured directory") from exc
    if not resolved.is_file():
        raise ValueError("model artifact file does not exist")
    return resolved


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _json_dict(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}
