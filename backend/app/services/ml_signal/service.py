from __future__ import annotations

import hashlib
import json
import math
import pickle
import posixpath
import shutil
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import BACKEND_DIR, get_settings
from app.models.entities import BacktestTrade, DailyBarSnapshot, Instrument, MLSignalModel, MLSignalSample, PaperTrade, RuntimeTask
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
    "price_momentum_5d",
    "price_momentum_10d",
    "volume_slope_5d",
    "volume_slope_10d",
    "price_momentum_5d_z",
    "price_momentum_10d_z",
    "volume_slope_5d_z",
    "volume_slope_10d_z",
    "sector_relative_strength_5d",
    "sector_relative_strength_10d",
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
        self._sequence_feature_cache: dict[tuple[str, str], dict[str, float]] = {}

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
        recent_rows = self.db.execute(
            select(PaperTrade).order_by(PaperTrade.id.desc()).limit(max(limit * 4, 500))
        ).scalars().all()
        rows = list(reversed(recent_rows))
        samples: list[dict[str, Any]] = []
        ledger: dict[tuple[int, str], dict[str, float]] = {}
        for row in rows:
            key = (int(row.account_id or 0), str(row.symbol or ""))
            quantity = int(row.quantity or 0)
            if quantity <= 0:
                continue
            if row.side == "buy":
                position = ledger.setdefault(key, {"quantity": 0.0, "cost": 0.0})
                position["quantity"] += quantity
                position["cost"] += float(row.net_amount or row.gross_amount or 0)
                continue
            if row.side != "sell":
                continue
            position = ledger.get(key)
            if not position or position["quantity"] <= 0:
                continue
            matched_quantity = min(quantity, int(position["quantity"]))
            if matched_quantity <= 0:
                continue
            avg_cost = position["cost"] / max(position["quantity"], 1.0)
            cost_basis = avg_cost
            fee_amount = float(row.commission or 0) + float(row.stamp_tax or 0) + float(row.transfer_fee or 0)
            pnl_amount = (float(row.price or 0) - cost_basis) * matched_quantity - fee_amount
            return_pct = (float(row.price or 0) / cost_basis - 1.0) * 100 if cost_basis > 0 else 0.0
            trade_date = row.trade_time.date().isoformat() if row.trade_time else ""
            samples.append(
                {
                    "sample_key": f"paper_close:{row.id}",
                    "symbol": row.symbol,
                    "trade_date": trade_date,
                    "strategy_key": row.strategy_key,
                    "source": "paper",
                    "features": _trade_features(
                        price=float(row.price or 0),
                        quantity=matched_quantity,
                        gross_amount=float(row.gross_amount or 0),
                        strategy_key=row.strategy_key,
                        market_state=row.market_state,
                        side=row.side,
                        sequence_features=self._sequence_features(row.symbol, trade_date),
                    ),
                    "label": {
                        "closed": True,
                        "side": row.side,
                        "cost_basis": round(cost_basis, 6),
                        "pnl_amount": round(pnl_amount, 6),
                        "return_pct": round(return_pct, 6),
                        "pnl_pct": round(return_pct, 6),
                        "paper_trade_id": row.id,
                        "paper_order_id": row.order_id,
                        "account_id": row.account_id,
                        "exit_reason": row.exit_reason,
                    },
                }
            )
            position["quantity"] -= matched_quantity
            position["cost"] = max(position["quantity"], 0.0) * avg_cost
            if len(samples) >= limit:
                break
        return list(reversed(samples))

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
                    sequence_features=self._sequence_features(row.symbol, row.trade_date),
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

    def _sequence_features(self, symbol: str, trade_date: str) -> dict[str, float]:
        key = (str(symbol or ""), str(trade_date or ""))
        if not key[0] or not key[1]:
            return _empty_sequence_features()
        cached = self._sequence_feature_cache.get(key)
        if cached is not None:
            return cached
        rows = (
            self.db.execute(
                select(DailyBarSnapshot)
                .where(DailyBarSnapshot.symbol == key[0])
                .where(DailyBarSnapshot.trade_date <= key[1])
                .order_by(DailyBarSnapshot.trade_date.desc())
                .limit(80)
            )
            .scalars()
            .all()
        )
        features = _sequence_features_from_bars(list(reversed(rows)))
        features.update(self._sector_relative_strength(key[0], list(reversed(rows))))
        self._sequence_feature_cache[key] = features
        return features

    def _sector_relative_strength(self, symbol: str, rows: list[DailyBarSnapshot]) -> dict[str, float]:
        if len(rows) < 11:
            return {
                "sector_relative_strength_5d": 0.0,
                "sector_relative_strength_10d": 0.0,
            }
        instrument = self.db.execute(select(Instrument).where(Instrument.symbol == symbol)).scalar_one_or_none()
        sector = str(instrument.sector_name or "").strip() if instrument is not None else ""
        if not sector:
            return {
                "sector_relative_strength_5d": 0.0,
                "sector_relative_strength_10d": 0.0,
            }
        peers = (
            self.db.execute(
                select(Instrument.symbol)
                .where(Instrument.sector_name == sector)
                .where(Instrument.instrument_type == "stock")
                .limit(120)
            )
            .scalars()
            .all()
        )
        peer_symbols = [item for item in peers if item and item != symbol]
        if not peer_symbols:
            return {
                "sector_relative_strength_5d": 0.0,
                "sector_relative_strength_10d": 0.0,
            }
        trade_dates = [str(row.trade_date) for row in rows[-11:]]
        peer_rows = (
            self.db.execute(
                select(DailyBarSnapshot)
                .where(DailyBarSnapshot.symbol.in_(peer_symbols))
                .where(DailyBarSnapshot.trade_date.in_(trade_dates))
            )
            .scalars()
            .all()
        )
        by_symbol: dict[str, dict[str, float]] = {}
        for row in peer_rows:
            if float(row.close_price or 0.0) <= 0:
                continue
            by_symbol.setdefault(str(row.symbol), {})[str(row.trade_date)] = float(row.close_price or 0.0)
        symbol_closes = {str(row.trade_date): float(row.close_price or 0.0) for row in rows if float(row.close_price or 0.0) > 0}

        def relative(days: int) -> float:
            if len(trade_dates) <= days:
                return 0.0
            start_date = trade_dates[-days - 1]
            end_date = trade_dates[-1]
            own_start = symbol_closes.get(start_date, 0.0)
            own_end = symbol_closes.get(end_date, 0.0)
            if own_start <= 0 or own_end <= 0:
                return 0.0
            own_momentum = (own_end / own_start - 1.0) * 100
            peer_momentum: list[float] = []
            for values in by_symbol.values():
                start = values.get(start_date, 0.0)
                end = values.get(end_date, 0.0)
                if start > 0 and end > 0:
                    peer_momentum.append((end / start - 1.0) * 100)
            if not peer_momentum:
                return 0.0
            return round(own_momentum - float(np.mean(peer_momentum)), 4)

        return {
            "sector_relative_strength_5d": relative(5),
            "sector_relative_strength_10d": relative(10),
        }


def _fit_estimator(*, model_type: str, x_matrix: np.ndarray, labels: np.ndarray, validation_ratio: float):
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
        folds=int(get_settings().ml_signal_cv_folds),
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

        return XGBClassifier(
            n_estimators=120,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.85,
            colsample_bytree=0.85,
            eval_metric="logloss",
            n_jobs=1,
            random_state=42,
        )
    if model_type == "lightgbm":
        from lightgbm import LGBMClassifier

        return LGBMClassifier(
            n_estimators=120,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.85,
            colsample_bytree=0.85,
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


def _promotion_blocks(*, payload: MLSignalTrainRequest, metrics: dict[str, Any], sample_count: int) -> list[str]:
    settings = get_settings()
    blocks: list[str] = []
    min_samples = max(int(settings.ml_signal_min_production_samples), int(payload.min_samples))
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


def _production_model_warning(status: str, metrics: dict[str, Any]) -> str:
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
    if sample_count < int(settings.ml_signal_min_production_samples):
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
    sequence_features: dict[str, float] | None = None,
) -> dict[str, Any]:
    features = {
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
    features.update(sequence_features or _empty_sequence_features())
    return features


def _empty_sequence_features() -> dict[str, float]:
    return {
        "price_momentum_5d": 0.0,
        "price_momentum_10d": 0.0,
        "volume_slope_5d": 0.0,
        "volume_slope_10d": 0.0,
        "price_momentum_5d_z": 0.0,
        "price_momentum_10d_z": 0.0,
        "volume_slope_5d_z": 0.0,
        "volume_slope_10d_z": 0.0,
        "sector_relative_strength_5d": 0.0,
        "sector_relative_strength_10d": 0.0,
    }


def _sequence_features_from_bars(rows: list[DailyBarSnapshot]) -> dict[str, float]:
    if not rows:
        return _empty_sequence_features()
    closes = [float(row.close_price or 0.0) for row in rows if float(row.close_price or 0.0) > 0]
    volumes = [float(row.volume or 0.0) for row in rows if float(row.volume or 0.0) >= 0]
    latest_close = closes[-1] if closes else 0.0

    def momentum_at(index: int, days: int) -> float:
        if index - days < 0:
            return 0.0
        start = closes[index - days]
        end = closes[index]
        if start <= 0 or end <= 0:
            return 0.0
        return (end / start - 1.0) * 100

    def momentum(days: int) -> float:
        if latest_close <= 0 or len(closes) <= days or closes[-days - 1] <= 0:
            return 0.0
        return round(momentum_at(len(closes) - 1, days), 4)

    def slope_for_series(series: list[float]) -> float:
        if len(series) < 3:
            return 0.0
        avg_volume = float(np.mean(series)) or 1.0
        x_values = np.arange(len(series), dtype=float)
        coef = float(np.polyfit(x_values, np.asarray(series, dtype=float), 1)[0])
        return coef / avg_volume

    def slope(days: int) -> float:
        series = volumes[-days:] if len(volumes) >= days else volumes
        return round(slope_for_series(series), 6)

    def rolling_momentum_z(days: int) -> float:
        values = [momentum_at(index, days) for index in range(days, len(closes))]
        return _zscore(values[-1] if values else 0.0, values)

    def rolling_slope_z(days: int) -> float:
        values = [slope_for_series(volumes[max(0, index - days + 1) : index + 1]) for index in range(days - 1, len(volumes))]
        return _zscore(values[-1] if values else 0.0, values)

    return {
        "price_momentum_5d": momentum(5),
        "price_momentum_10d": momentum(10),
        "volume_slope_5d": slope(5),
        "volume_slope_10d": slope(10),
        "price_momentum_5d_z": rolling_momentum_z(5),
        "price_momentum_10d_z": rolling_momentum_z(10),
        "volume_slope_5d_z": rolling_slope_z(5),
        "volume_slope_10d_z": rolling_slope_z(10),
    }


def _label_is_positive(label: dict[str, Any]) -> bool:
    if "return_pct" in label:
        return _to_float(label.get("return_pct")) > 0
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
        remote_artifact_uri=row.remote_artifact_uri,
        artifact_checksum=row.artifact_checksum,
        created_at=row.created_at,
    )


def _model_effective_status(row: MLSignalModel) -> str:
    metrics = _json_dict(row.metrics_json)
    if row.status != "production":
        return row.status
    if not row.artifact_uri or not (row.artifact_checksum or metrics.get("artifact_sha256")):
        return "research"
    return "research" if _production_model_warning("production", metrics) else "production"


def _label(probability: float) -> str:
    if probability >= 0.62:
        return "positive"
    if probability <= 0.38:
        return "negative"
    return "neutral"


def _zscore(value: float, values: list[float]) -> float:
    if len(values) < 5:
        return 0.0
    array = np.asarray([item for item in values if math.isfinite(float(item))], dtype=float)
    if len(array) < 5:
        return 0.0
    std = float(np.std(array))
    if std <= 1e-9:
        return 0.0
    return round((float(value) - float(np.mean(array))) / std, 4)


def _safe_float(value: Decimal | float | int | str | None) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


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


def _is_fsspec_uri(value: str) -> bool:
    return "://" in str(value or "") and not str(value or "").startswith("file://")


def _join_fsspec_uri(base_uri: str, filename: str) -> str:
    cleaned = str(base_uri).rstrip("/")
    return f"{cleaned}/{filename}"


def _fsspec_url_to_fs(uri: str):
    try:
        import fsspec
    except ImportError as exc:
        raise ValueError(
            "ml_signal_artifact_remote_dir uses a remote URI; install fsspec and the matching storage driver "
            "(for example s3fs/ossfs) to enable remote ML artifacts."
        ) from exc
    return fsspec.core.url_to_fs(uri)


def _copy_local_to_fsspec(source: Path, target_uri: str) -> None:
    fs, target_path = _fsspec_url_to_fs(target_uri)
    parent = posixpath.dirname(target_path)
    if parent:
        fs.makedirs(parent, exist_ok=True)
    with source.open("rb") as src, fs.open(target_path, "wb") as dst:
        shutil.copyfileobj(src, dst)


def _copy_fsspec_to_local(source_uri: str, target: Path) -> None:
    fs, source_path = _fsspec_url_to_fs(source_uri)
    if not fs.exists(source_path):
        raise ValueError("remote model artifact file does not exist")
    with fs.open(source_path, "rb") as src, target.open("wb") as dst:
        shutil.copyfileobj(src, dst)


def _fsspec_sha256(uri: str) -> str:
    fs, path = _fsspec_url_to_fs(uri)
    if not fs.exists(path):
        raise ValueError("remote model artifact file does not exist")
    digest = hashlib.sha256()
    with fs.open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _remove_fsspec_file(uri: str) -> None:
    fs, path = _fsspec_url_to_fs(uri)
    if fs.exists(path):
        fs.rm(path)


def _mask_storage_uri(value: str) -> str:
    if "://" not in value:
        return value
    scheme, rest = value.split("://", 1)
    if "@" not in rest:
        return value
    return f"{scheme}://***@{rest.rsplit('@', 1)[-1]}"


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
