from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import MLSignalModel, User
from app.models.schema_defs.phase4 import MLSignalModelOut
from app.services.ml_signal.modeling import json_dict, json_dumps, model_out, production_model_warning
from app.services.operation_audit import record_operation_audit


class MLSignalPromotionService:
    """Manual approval boundary for ML model promotion."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def approve(self, model_key: str, *, operator: User | str | None = None) -> MLSignalModelOut:
        row = self.db.execute(select(MLSignalModel).where(MLSignalModel.model_key == model_key)).scalar_one_or_none()
        if row is None:
            raise ValueError(f"模型不存在：{model_key}")
        metrics = json_dict(row.metrics_json)
        if not metrics.get("promotion_candidate"):
            blocked = str(metrics.get("promotion_blocked_reason") or "模型未达到晋级门槛。")
            raise ValueError(blocked)
        if not row.artifact_uri or not (row.artifact_checksum or metrics.get("artifact_sha256")):
            raise ValueError("模型 artifact 不完整，不能进入 production。")
        current_warning = production_model_warning("production", metrics)
        if current_warning:
            raise ValueError(f"当前生产门槛复核失败：{current_warning}")
        self.db.execute(
            MLSignalModel.__table__.update()
            .where(MLSignalModel.status == "production", MLSignalModel.model_key != model_key)
            .values(status="archived")
        )
        operator_name = _operator_name(operator)
        metrics["approval_required"] = False
        metrics["approved_by"] = operator_name
        metrics["approved_at"] = datetime.utcnow().isoformat(timespec="seconds")
        metrics["deployment_stage"] = "production"
        metrics["model_version_status"] = "production"
        metrics["shadow_traffic_pct"] = 0.0
        metrics["canary_traffic_pct"] = 0.0
        metrics["production_traffic_pct"] = 100.0
        row.status = "production"
        row.metrics_json = json_dumps(metrics)
        self.db.commit()
        record_operation_audit(
            self.db,
            operation="ml_model_promote",
            user=operator if isinstance(operator, User) else None,
            resource_type="ml_signal_model",
            resource_id=model_key,
            detail={
                "model_key": model_key,
                "status": row.status,
                "cv_auc": metrics.get("cv_auc"),
                "cv_accuracy": metrics.get("cv_accuracy"),
                "artifact_checksum": row.artifact_checksum or metrics.get("artifact_sha256") or "",
                "approved_at": metrics.get("approved_at"),
                "approved_by": operator_name,
                "approved_by_user_id": getattr(operator, "id", None) if isinstance(operator, User) else None,
            },
        )
        self.db.commit()
        self.db.refresh(row)
        return model_out(row)


def _operator_name(operator: User | str | None) -> str:
    if operator is None:
        return "unknown"
    if isinstance(operator, str):
        return operator.strip() or "unknown"
    username = str(getattr(operator, "username", "") or "").strip()
    if username:
        return username
    phone = str(getattr(operator, "phone", "") or "").strip()
    if phone:
        return phone
    user_id = getattr(operator, "id", None)
    return f"user:{user_id}" if user_id is not None else "unknown"
