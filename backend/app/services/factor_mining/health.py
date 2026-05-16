from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.entities import FactorDefinitionEntity, FactorEvalRunEntity
from app.services.factor_mining.json_utils import json_dict


class FactorHealthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def dashboard(self, *, limit: int = 50) -> dict:
        rows = self.db.execute(
            select(FactorDefinitionEntity).order_by(FactorDefinitionEntity.updated_at.desc()).limit(limit)
        ).scalars().all()
        items = [self._item(row) for row in rows]
        return {
            "total": len(items),
            "production": sum(1 for item in items if item["status"] == "production"),
            "validated": sum(1 for item in items if item["status"] == "validated"),
            "items": items,
        }

    def _item(self, row: FactorDefinitionEntity) -> dict:
        latest_runs = self.db.execute(
            select(FactorEvalRunEntity)
            .where(FactorEvalRunEntity.factor_key == row.factor_key)
            .order_by(desc(FactorEvalRunEntity.created_at))
            .limit(8)
        ).scalars().all()
        ic_values = [float(json_dict(run.metrics_json).get("ic_mean") or 0.0) for run in latest_runs]
        trend = "stable"
        if len(ic_values) >= 2 and ic_values[0] < ic_values[-1] - 0.01:
            trend = "decaying"
        elif len(ic_values) >= 2 and ic_values[0] > ic_values[-1] + 0.01:
            trend = "improving"
        metrics = json_dict(row.eval_result_json)
        return {
            "factor_key": row.factor_key,
            "name": row.name,
            "status": row.status,
            "ic_mean": metrics.get("ic_mean", 0.0),
            "ic_t_stat": metrics.get("ic_t_stat", 0.0),
            "trend": trend,
            "run_count": len(latest_runs),
        }
