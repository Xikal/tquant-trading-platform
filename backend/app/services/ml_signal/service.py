from __future__ import annotations

import pickle
import shutil
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import BACKEND_DIR, get_settings
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
from app.services.ml_signal.artifact_storage import (
    copy_fsspec_to_local as _copy_fsspec_to_local,
    copy_local_to_fsspec as _copy_local_to_fsspec,
    file_sha256 as _file_sha256,
    fsspec_sha256 as _fsspec_sha256,
    is_fsspec_uri as _is_fsspec_uri,
    join_fsspec_uri as _join_fsspec_uri,
    mask_storage_uri as _mask_storage_uri,
    remove_fsspec_file as _remove_fsspec_file,
    safe_artifact_name as _safe_artifact_name,
    validated_artifact_path as _validated_artifact_path,
)
from app.services.ml_signal.features import (
    FEATURE_NAMES,
    estimator_probabilities as _estimator_probabilities,
    label_is_positive as _label_is_positive,
    predict_probability as _predict_probability,
    safe_float as _safe_float,
    samples_to_matrix as _samples_to_matrix,
    signal_label as _label,
    to_float as _to_float,
    trade_features as _trade_features,
)
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

HEURISTIC_MODEL_KEY = "research-heuristic-v1"


class MLSignalService:
    """ML signal model service with research and production boundaries.

    The service can train/register models and serve promoted production models,
    but it remains an advisory signal surface. Trading permission, T+1, sizing
    and stop rules must still be enforced by deterministic backend risk logic.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self._sample_repository = MLSignalSampleRepository(db)

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
            promote=False,
            model_key=f"paper-incremental-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        )
        if train_payload.source != "paper":
            train_payload = train_payload.model_copy(update={"source": "paper"})
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
        row.feature_schema_json = _json_dumps({"feature_names": FEATURE_NAMES})
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
                .where(RuntimeTask.task_type == "ml_signal_incremental_train")
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
            warnings=warnings,
        )

    def predict(self, payload: MLSignalPredictionRequest) -> MLSignalPredictionResponse:
        row = self._select_model(payload.model_key)
        if row is not None and row.artifact_uri:
            try:
                metrics = _json_dict(row.metrics_json)
                artifact = self._load_artifact(
                    row.artifact_uri,
                    expected_sha256=str(row.artifact_checksum or metrics.get("artifact_sha256") or ""),
                    remote_artifact_uri=str(row.remote_artifact_uri or metrics.get("remote_artifact_uri") or ""),
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

    def check_artifact_storage(self) -> MLSignalArtifactStorageCheckResponse:
        """Validate configured artifact storage with write/read/restore/cleanup probes."""

        remote_dir_raw = (get_settings().ml_signal_artifact_remote_dir or "").strip()
        if not remote_dir_raw:
            return MLSignalArtifactStorageCheckResponse(
                ok=True,
                configured=False,
                backend="local",
                message="未配置远端模型存储，当前仅使用本地 artifact 目录。",
            )
        artifact_dir = self._artifact_dir()
        probe_name = f"storage_probe_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}.pkl"
        local_source = artifact_dir / probe_name
        local_restore = artifact_dir / f"restore_{probe_name}"
        with local_source.open("wb") as file:
            pickle.dump({"probe": "tquant_ml_artifact_storage", "created_at": datetime.utcnow().isoformat()}, file)
        expected_sha256 = _file_sha256(local_source)
        try:
            if _is_fsspec_uri(remote_dir_raw):
                backend = "fsspec"
                remote_uri = _join_fsspec_uri(remote_dir_raw, probe_name)
                _copy_local_to_fsspec(local_source, remote_uri)
                read_ok = _fsspec_sha256(remote_uri) == expected_sha256
                if read_ok:
                    _copy_fsspec_to_local(remote_uri, local_restore)
                restore_ok = local_restore.exists() and _file_sha256(local_restore) == expected_sha256
                _remove_fsspec_file(remote_uri)
                cleanup_ok = True
            else:
                backend = "filesystem"
                remote_dir = Path(remote_dir_raw)
                if not remote_dir.is_absolute():
                    remote_dir = BACKEND_DIR / remote_dir
                remote_dir.mkdir(parents=True, exist_ok=True)
                remote_path = remote_dir / probe_name
                shutil.copy2(local_source, remote_path)
                read_ok = _file_sha256(remote_path) == expected_sha256
                if read_ok:
                    shutil.copy2(remote_path, local_restore)
                restore_ok = local_restore.exists() and _file_sha256(local_restore) == expected_sha256
                remote_path.unlink(missing_ok=True)
                cleanup_ok = not remote_path.exists()
            ok = bool(read_ok and restore_ok and cleanup_ok)
            return MLSignalArtifactStorageCheckResponse(
                ok=ok,
                configured=True,
                backend=backend,
                remote_dir=_mask_storage_uri(remote_dir_raw),
                write_ok=True,
                read_ok=read_ok,
                restore_ok=restore_ok,
                cleanup_ok=cleanup_ok,
                message="远端模型存储写入、读取、恢复、清理验收通过。" if ok else "远端模型存储验收未完全通过。",
            )
        except Exception as exc:
            return MLSignalArtifactStorageCheckResponse(
                ok=False,
                configured=True,
                backend="fsspec" if _is_fsspec_uri(remote_dir_raw) else "filesystem",
                remote_dir=_mask_storage_uri(remote_dir_raw),
                message=f"远端模型存储验收失败：{exc}",
            )
        finally:
            local_source.unlink(missing_ok=True)
            local_restore.unlink(missing_ok=True)

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

    def _backup_artifact(self, artifact_uri: str, expected_sha256: str) -> str:
        remote_dir_raw = (get_settings().ml_signal_artifact_remote_dir or "").strip()
        if not remote_dir_raw:
            return ""
        source = _validated_artifact_path(artifact_uri, self._artifact_dir())
        if _is_fsspec_uri(remote_dir_raw):
            target_uri = _join_fsspec_uri(remote_dir_raw, source.name)
            _copy_local_to_fsspec(source, target_uri)
            if _fsspec_sha256(target_uri) != expected_sha256:
                _remove_fsspec_file(target_uri)
                raise ValueError("remote artifact hash mismatch after backup")
            return target_uri
        remote_dir = Path(remote_dir_raw)
        if not remote_dir.is_absolute():
            remote_dir = BACKEND_DIR / remote_dir
        remote_dir.mkdir(parents=True, exist_ok=True)
        target = remote_dir / source.name
        if source.resolve() == target.resolve():
            return str(target)
        shutil.copy2(source, target)
        if _file_sha256(target) != expected_sha256:
            target.unlink(missing_ok=True)
            raise ValueError("remote artifact hash mismatch after backup")
        return str(target)

    def _load_artifact(
        self,
        artifact_uri: str,
        *,
        expected_sha256: str = "",
        remote_artifact_uri: str = "",
    ) -> dict[str, Any]:
        self._restore_artifact_if_missing(
            artifact_uri=artifact_uri,
            remote_artifact_uri=remote_artifact_uri,
            expected_sha256=expected_sha256,
        )
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

    def _restore_artifact_if_missing(
        self,
        *,
        artifact_uri: str,
        remote_artifact_uri: str,
        expected_sha256: str,
    ) -> None:
        if not remote_artifact_uri or not expected_sha256:
            return
        target = Path(artifact_uri).expanduser()
        base = self._artifact_dir().resolve()
        target_resolved = target.resolve()
        try:
            target_resolved.relative_to(base)
        except ValueError as exc:
            raise ValueError("model artifact restore path escapes configured directory") from exc
        if target.exists():
            return
        if _is_fsspec_uri(remote_artifact_uri):
            if _fsspec_sha256(remote_artifact_uri) != expected_sha256:
                raise ValueError("remote model artifact hash mismatch")
            target.parent.mkdir(parents=True, exist_ok=True)
            _copy_fsspec_to_local(remote_artifact_uri, target)
            return
        remote = Path(remote_artifact_uri).expanduser()
        if not remote.is_file():
            return
        if _file_sha256(remote) != expected_sha256:
            raise ValueError("remote model artifact hash mismatch")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(remote, target)

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
