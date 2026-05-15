from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import MLSignalModel
from app.models.schema_defs.phase4 import MLSignalModelOut
from app.services.ml_signal.modeling import json_dict, json_dumps, model_out, production_model_warning


class MLSignalPromotionService:
    """Manual approval boundary for ML model promotion."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def approve(self, model_key: str, *, operator: str = "admin") -> MLSignalModelOut:
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
        metrics["approval_required"] = False
        metrics["approved_by"] = operator
        metrics["approved_at"] = datetime.utcnow().isoformat(timespec="seconds")
        row.status = "production"
        row.metrics_json = json_dumps(metrics)
        self.db.commit()
        self.db.refresh(row)
        return model_out(row)
