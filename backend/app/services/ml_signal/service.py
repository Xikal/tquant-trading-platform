from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import MLSignalModel, MLSignalSample, PaperTrade, RuntimeTask
from app.models.schema_defs.phase4 import (
    MLSignalArtifactStorageCheckResponse,
    MLSignalModelListResponse,
    MLSignalModelOut,
    MLSignalOnlineLearningStatusResponse,
    MLSignalPredictionRequest,
    MLSignalPredictionResponse,
    MLSignalSampleBuildRequest,
    MLSignalSampleBuildResponse,
    MLSignalTrainRequest,
    MLSignalTrainResponse,
)
from app.services.ml_signal.artifact_manager import MLSignalArtifactManager
from app.services.ml_signal.features import (
    FEATURE_NAMES,
    feature_missing_rates as _feature_missing_rates,
    label_is_positive as _label_is_positive,
    predict_probability as _predict_probability,
    safe_float as _safe_float,
    samples_to_matrix as _samples_to_matrix,
    signal_label as _label,
    trade_features as _trade_features,
)
from app.services.ml_signal import feature_schema as _feature_schema
from app.services.ml_signal.modeling import (
    fit_estimator as _fit_estimator,
    generated_model_key as _generated_model_key,
    json_dict as _json_dict,
    json_dumps as _json_dumps,
    model_effective_status as _model_effective_status,
    model_out as _model_out,
    production_model_warning as _production_model_warning,
    promotion_blocks as _promotion_blocks,
)
from app.services.ml_signal.sample_repository import MLSignalSampleRepository
from app.services.ml_signal.schedule_info import next_training_rule_text
from app.services.ml_signal.drift_monitor import feature_drift_summary
from app.services.ml_signal.time_series_validation import chronological_samples
from app.services.ml_signal.training_runtime import (
    incremental_model_type,
    incremental_promote_enabled,
    incremental_warm_start_enabled,
    max_validation_p_value,
    training_parameter_snapshot,
)
from app.services.ml_signal.prediction_fallback import HEURISTIC_MODEL_KEY, heuristic_predict
from app.services.ml_signal.warm_start import load_warm_start_estimator


class MLSignalService:
    """ML signal model service with research and production boundaries.

    The service can train/register models and serve promoted production models,
    but it remains an advisory signal surface. Trading permission, T+1, sizing
    and stop rules must still be enforced by deterministic backend risk logic.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self._sample_repository = MLSignalSampleRepository(db)
        self._artifact_manager = MLSignalArtifactManager()

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

    def incremental_train(self, payload: MLSignalTrainRequest | None = None) -> MLSignalTrainResponse:
        """Train from recent closed paper trades for the online-learning loop.

        This deliberately reuses the normal promotion gates.  Incremental
        training may produce a research model every week, but it still cannot
        enter production unless sample size, validation and K-fold quality pass.
        """

        train_payload = payload or MLSignalTrainRequest(
            source="paper",
            limit=5000,
            min_samples=100,
            model_type=incremental_model_type(),  # type: ignore[arg-type]
            promote=incremental_promote_enabled(),
            warm_start=incremental_warm_start_enabled(),
            max_validation_p_value=max_validation_p_value(),
            model_key=f"paper-incremental-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        )
        if train_payload.source != "paper":
            train_payload = train_payload.model_copy(update={"source": "paper"})
        if not train_payload.model_key:
            train_payload = train_payload.model_copy(
                update={"model_key": f"paper-incremental-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"}
            )
        return self.train(train_payload)

    def persist_paper_trade_outcome(
        self,
        trade: PaperTrade,
        *,
        cost_basis: Decimal | float,
        pnl_amount: Decimal | float,
        return_pct: Decimal | float,
        label_note: str = "",
    ) -> bool:
        """Persist a closed paper-trade outcome as an ML sample.

        Called from the paper-trading transaction after a sell trade is matched.
        The method does not commit; it participates in the caller transaction.
        """

        if str(trade.side or "").lower() != "sell":
            return False
        sample = {
            "sample_key": f"paper_close:{trade.id or trade.order_id}",
            "symbol": trade.symbol,
            "trade_date": trade.trade_time.date().isoformat() if trade.trade_time else datetime.utcnow().date().isoformat(),
            "strategy_key": trade.strategy_key,
            "source": "paper",
            "features": _trade_features(
                price=float(trade.price or 0),
                quantity=int(trade.quantity or 0),
                gross_amount=float(trade.gross_amount or 0),
                strategy_key=trade.strategy_key,
                market_state=trade.market_state,
                side=trade.side,
                sequence_features=self._sequence_features(
                    trade.symbol,
                    trade.trade_time.date().isoformat() if trade.trade_time else datetime.utcnow().date().isoformat(),
                ),
            ),
            "label": {
                "closed": True,
                "side": trade.side,
                "cost_basis": _safe_float(cost_basis),
                "pnl_amount": _safe_float(pnl_amount),
                "return_pct": _safe_float(return_pct),
                "pnl_pct": _safe_float(return_pct),
                "paper_trade_id": trade.id or 0,
                "paper_order_id": trade.order_id or 0,
                "account_id": trade.account_id or 0,
                "exit_reason": trade.exit_reason or "",
                "label_note": label_note,
            },
        }
        return self._persist_sample(sample)

    def train(self, payload: MLSignalTrainRequest) -> MLSignalTrainResponse:
        rows = chronological_samples(self._load_training_samples(source=payload.source, limit=payload.limit))
        min_samples = int(payload.min_samples)
        if len(rows) < min_samples:
            return MLSignalTrainResponse(
                model_key=payload.model_key or _generated_model_key(payload.model_type),
                model_type=payload.model_type,
                status="failed",
                sample_count=len(rows),
                feature_names=FEATURE_NAMES,
                warning=f"样本量不足：当前 {len(rows)}，最低需要 {min_samples}。",
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
            warm_start_estimator = self._warm_start_estimator(payload) if payload.warm_start else None
            estimator, metrics = _fit_estimator(
                model_type=payload.model_type,
                x_matrix=x_matrix,
                labels=labels,
                validation_ratio=payload.validation_ratio,
                warm_start_estimator=warm_start_estimator,
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
        metrics["quant_parameter"] = training_parameter_snapshot(self.db)
        metrics["feature_missing_rates"] = _feature_missing_rates(rows)
        metrics["warm_start_enabled"] = bool(payload.warm_start)
        promotion_blocks = _promotion_blocks(payload=payload, metrics=metrics, sample_count=len(rows))
        promotion_candidate = not promotion_blocks
        metrics["promotion_candidate"] = bool(promotion_candidate)
        metrics["approval_required"] = bool(promotion_candidate and not payload.promote)
        if promotion_blocks:
            metrics["promotion_blocked_reason"] = "；".join(promotion_blocks)
        can_promote = payload.promote and promotion_candidate
        status = "production" if can_promote else "research"
        _feature_schema.add_model_version_metadata(metrics, status=status, promotion_candidate=promotion_candidate, promote_requested=payload.promote)
        metrics["model_version_id"] = model_key
        schema_payload = _feature_schema.feature_schema_payload(FEATURE_NAMES)
        artifact_uri, artifact_sha256 = self._save_artifact(
            model_key=model_key,
            payload={
                "model_key": model_key,
                "model_type": payload.model_type,
                "feature_names": FEATURE_NAMES,
                "feature_schema": schema_payload,
                "feature_schema_hash": schema_payload["feature_schema_hash"],
                "deployment_stage": metrics["deployment_stage"],
                "estimator": estimator,
                "metrics": metrics,
                "created_at": datetime.utcnow().isoformat(),
            },
        )
        metrics["artifact_sha256"] = artifact_sha256
        remote_artifact_uri = self._backup_artifact(artifact_uri, artifact_sha256)
        if remote_artifact_uri:
            metrics["remote_artifact_uri"] = remote_artifact_uri
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
        row.feature_schema_json = _json_dumps(schema_payload)
        row.metrics_json = _json_dumps(metrics)
        row.artifact_uri = artifact_uri
        row.remote_artifact_uri = remote_artifact_uri
        row.artifact_checksum = artifact_sha256
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
            remote_artifact_uri=row.remote_artifact_uri,
            artifact_checksum=row.artifact_checksum,
            warning=_train_warning(status, metrics),
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

    def online_learning_status(self, min_samples: int = 100) -> MLSignalOnlineLearningStatusResponse:
        """Return the operational state of the paper-trade online learning loop."""

        paper_sample_count = int(
            self.db.execute(
                select(func.count(MLSignalSample.id)).where(MLSignalSample.source == "paper")
            ).scalar_one()
            or 0
        )
        recent_samples = (
            self.db.execute(
                select(MLSignalSample)
                .where(MLSignalSample.source == "paper")
                .order_by(MLSignalSample.id.desc())
                .limit(max(min_samples * 5, 500))
            )
            .scalars()
            .all()
        )
        closed_trade_sample_count = 0
        positive_count = 0
        negative_count = 0
        for row in recent_samples:
            label = _json_dict(row.label_json)
            if label.get("closed") is True or str(row.sample_key or "").startswith("paper_close:"):
                closed_trade_sample_count += 1
                if _label_is_positive(label):
                    positive_count += 1
                else:
                    negative_count += 1

        latest_model = self.db.execute(select(MLSignalModel).order_by(MLSignalModel.id.desc()).limit(1)).scalar_one_or_none()
        model_list = self.list_models(limit=20)
        latest_task = (
            self.db.execute(
                select(RuntimeTask)
                .where(RuntimeTask.task_type.in_(("ml_signal_incremental_train", "strategy_self_evolution")))
                .order_by(RuntimeTask.id.desc())
                .limit(1)
            )
            .scalar_one_or_none()
        )
        warnings: list[str] = []
        if paper_sample_count < min_samples:
            warnings.append(f"paper 样本不足：当前 {paper_sample_count}，最低需要 {min_samples}。")
        if positive_count == 0 or negative_count == 0:
            warnings.append("近期闭环样本正负类别不完整，增量训练会被生产门槛拦截。")
        if latest_task is None:
            warnings.append("尚未发现每周增量训练任务记录，等待调度周期或手动触发。")
        drift = feature_drift_summary(recent_samples)
        warnings.extend(drift.get("alerts", [])[:3])

        return MLSignalOnlineLearningStatusResponse(
            generated_at=datetime.utcnow().isoformat(timespec="seconds"),
            paper_sample_count=paper_sample_count,
            closed_trade_sample_count=closed_trade_sample_count,
            positive_sample_count=positive_count,
            negative_sample_count=negative_count,
            ready_for_training=paper_sample_count >= min_samples and positive_count > 0 and negative_count > 0,
            min_samples=min_samples,
            feature_names=FEATURE_NAMES,
            sequence_feature_names=[name for name in FEATURE_NAMES if name.startswith(("price_momentum", "volume_slope", "sector_relative"))],
            latest_model=_model_out(latest_model) if latest_model is not None else None,
            production_model_key=model_list.production_model_key,
            latest_incremental_task_id=latest_task.id if latest_task is not None else None,
            latest_incremental_task_status=latest_task.status if latest_task is not None else "",
            latest_incremental_task_progress_pct=float(latest_task.progress_pct or 0.0) if latest_task is not None else 0.0,
            latest_incremental_task_finished_at=latest_task.finished_at if latest_task is not None else None,
            next_training_rule=next_training_rule_text(),
            warnings=warnings,
            drift_ready=bool(drift.get("ready")),
            drift_alerts=list(drift.get("alerts") or []),
            drift_items=list(drift.get("items") or []),
        )

    def predict(self, payload: MLSignalPredictionRequest) -> MLSignalPredictionResponse:
        row = self._select_model(payload.model_key)
        if row is not None and row.artifact_uri:
            try:
                metrics = _json_dict(row.metrics_json)
                row_schema = _json_dict(row.feature_schema_json)
                artifact = self._load_artifact(
                    row.artifact_uri,
                    expected_sha256=str(row.artifact_checksum or metrics.get("artifact_sha256") or ""),
                    remote_artifact_uri=str(row.remote_artifact_uri or metrics.get("remote_artifact_uri") or ""),
                )
                schema_warning = _feature_schema.feature_schema_warning(artifact=artifact, metrics=metrics, row_schema=row_schema)
                if schema_warning:
                    return self._heuristic_predict(payload, warning=schema_warning)
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
                        "线上特征签名与训练 artifact 已校验一致。",
                        "输出仅作为信号因子，执行仍需后端风控确认。",
                    ],
                    metrics=metrics,
                    warning=quality_warning or ("" if row.status == "production" else "模型未进入 production，仅用于研究和观察。"),
                )
            except Exception as exc:
                return self._heuristic_predict(payload, warning=f"模型加载或推理失败，已降级启发式：{exc}")
        return self._heuristic_predict(payload)

    def check_artifact_storage(self) -> MLSignalArtifactStorageCheckResponse:
        """Validate configured artifact storage with write/read/restore/cleanup probes."""
        return self._artifact_manager.check_storage()

    def _heuristic_predict(self, payload: MLSignalPredictionRequest, warning: str = "") -> MLSignalPredictionResponse:
        return heuristic_predict(payload, warning=warning)

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

    def _warm_start_estimator(self, payload: MLSignalTrainRequest):
        return load_warm_start_estimator(payload, select_model=self._select_model, load_artifact=self._load_artifact)

    def _load_training_samples(self, *, source: str, limit: int) -> list[MLSignalSample]:
        statement = select(MLSignalSample)
        if source in {"paper", "backtest"}:
            statement = statement.where(MLSignalSample.source == source)
        return self.db.execute(statement.order_by(MLSignalSample.id.desc()).limit(limit)).scalars().all()

    def _artifact_dir(self) -> Path:
        return self._artifact_manager.artifact_dir()

    def _save_artifact(self, *, model_key: str, payload: dict[str, Any]) -> tuple[str, str]:
        return self._artifact_manager.save_artifact(model_key=model_key, payload=payload)

    def _backup_artifact(self, artifact_uri: str, expected_sha256: str) -> str:
        return self._artifact_manager.backup_artifact(artifact_uri, expected_sha256)

    def _load_artifact(
        self,
        artifact_uri: str,
        *,
        expected_sha256: str = "",
        remote_artifact_uri: str = "",
    ) -> dict[str, Any]:
        return self._artifact_manager.load_artifact(
            artifact_uri,
            expected_sha256=expected_sha256,
            remote_artifact_uri=remote_artifact_uri,
        )

    def _restore_artifact_if_missing(
        self,
        *,
        artifact_uri: str,
        remote_artifact_uri: str,
        expected_sha256: str,
    ) -> None:
        self._artifact_manager.restore_artifact_if_missing(
            artifact_uri=artifact_uri,
            remote_artifact_uri=remote_artifact_uri,
            expected_sha256=expected_sha256,
        )

    def _paper_samples(self, limit: int) -> list[dict[str, Any]]:
        return self._sample_repository.paper_samples(limit)

    def _backtest_samples(self, limit: int) -> list[dict[str, Any]]:
        return self._sample_repository.backtest_samples(limit)

    def _persist_sample(self, sample: dict[str, Any]) -> bool:
        return self._sample_repository.persist_sample(sample)

    def _sequence_features(self, symbol: str, trade_date: str) -> dict[str, float]:
        return self._sample_repository.sequence_features(symbol, trade_date)

    def _sector_relative_strength(self, symbol: str, rows) -> dict[str, float]:
        return self._sample_repository.sector_relative_strength(symbol, rows)


def _train_warning(status: str, metrics: dict[str, Any]) -> str:
    if status == "production":
        return ""
    if metrics.get("approval_required"):
        return "模型已达到晋级候选门槛，等待管理员审批后才可进入 production。"
    blocked = str(metrics.get("promotion_blocked_reason") or "")
    if blocked:
        return f"模型已训练但未进入 production：{blocked}"
    return "模型已训练但未进入 production，当前仍按研究模型使用。"
