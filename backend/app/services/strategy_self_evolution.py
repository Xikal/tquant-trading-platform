from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_now
from app.models.backtest_entities import BacktestValidation
from app.models.entities import QuantParameterSet
from app.models.schema_defs.phase4 import MLSignalIncrementalTrainRequest
from app.services.backtest.regime_parameter_promotion import promote_regime_parameter_versions
from app.services.low_buy.strategy_governance import build_low_buy_strategy_governance
from app.services.ml_signal import MLSignalService


class StrategySelfEvolutionOrchestrator:
    """Run the offline self-evolution loop without auto-promoting production state."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def run(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        operator = str(payload.get("operator") or "strategy-self-evolution")
        min_samples = int(payload.get("min_samples") or 100)
        ml_service = MLSignalService(self.db)
        training = ml_service.incremental_train(
            MLSignalIncrementalTrainRequest(
                model_key=str(payload.get("model_key") or ""),
                model_type=str(payload.get("model_type") or "xgboost"),  # type: ignore[arg-type]
                source="paper",
                limit=int(payload.get("limit") or 5000),
                min_samples=min_samples,
                validation_ratio=float(payload.get("validation_ratio") or 0.2),
                promote=False,
                warm_start=bool(payload.get("warm_start") if "warm_start" in payload else True),
                max_validation_p_value=float(payload.get("max_validation_p_value") or 0.05),
                min_validation_accuracy=float(payload.get("min_validation_accuracy") or 0.55),
            )
        )
        online_status = ml_service.online_learning_status(min_samples=min_samples)
        phase = self._phase_snapshot()
        parameter_proposal = self._propose_regime_parameters(operator=operator)
        metrics = dict(training.metrics or {})
        model_approval = {
            "required": bool(metrics.get("approval_required")),
            "model_key": training.model_key,
            "status": training.status,
            "candidate": bool(metrics.get("promotion_candidate")),
            "blocked_reason": str(metrics.get("promotion_blocked_reason") or ""),
            "message": training.warning,
        }
        return {
            "ok": True,
            "generated_at": beijing_now().isoformat(timespec="seconds"),
            "operator": operator,
            "training": training.model_dump(mode="json"),
            "model_approval": model_approval,
            "regime_parameter_promotion": parameter_proposal,
            "phase_evaluation": phase,
            "drift_monitor": {
                "ready": online_status.drift_ready,
                "alerts": online_status.drift_alerts,
                "items": online_status.drift_items[:12],
            },
            "online_learning": online_status.model_dump(mode="json"),
            "human_approval_required": bool(model_approval["required"])
            or int(parameter_proposal.get("promoted_count") or 0) > 0,
        }

    def run_drift_monitor(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        min_samples = int(payload.get("min_samples") or 100)
        status = MLSignalService(self.db).online_learning_status(min_samples=min_samples)
        return {
            "ok": True,
            "generated_at": beijing_now().isoformat(timespec="seconds"),
            "drift_ready": status.drift_ready,
            "drift_alerts": status.drift_alerts,
            "drift_items": status.drift_items,
            "sample_count": status.paper_sample_count,
        }

    def _phase_snapshot(self) -> list[dict[str, Any]]:
        governance = build_low_buy_strategy_governance(self.db)
        return [
            {
                "strategy_key": item.strategy_key,
                "strategy_title": item.strategy_title,
                "status": item.status,
                "health_score": item.strategy_health_score,
                "phase": item.validation_phase,
                "phase_text": item.validation_phase_text,
                "position_scale": item.validation_position_scale,
                "reason": item.validation_phase_reason,
            }
            for item in governance.items
        ]

    def _propose_regime_parameters(self, *, operator: str) -> dict[str, Any]:
        row = (
            self.db.execute(
                select(BacktestValidation)
                .where(
                    BacktestValidation.status == "succeeded",
                    BacktestValidation.deleted_at.is_(None),
                    BacktestValidation.result_json != "",
                    BacktestValidation.result_json != "{}",
                )
                .order_by(BacktestValidation.id.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        if row is None:
            return {"ok": True, "promoted_count": 0, "skipped": [{"reason": "没有可用样本外验证结果。"}]}
        if self._existing_parameter_proposal(row.id):
            return {
                "ok": True,
                "promoted_count": 0,
                "skipped": [{"reason": f"验证任务 {row.id} 已生成过参数草案，本轮跳过。"}],
            }
        try:
            result = json.loads(row.result_json or "{}")
        except Exception:
            return {"ok": False, "promoted_count": 0, "skipped": [{"reason": "样本外验证结果 JSON 无法解析。"}]}
        if not result.get("best_params_by_market_state"):
            return {"ok": True, "promoted_count": 0, "skipped": [{"reason": "验证结果未包含分市场状态最佳参数。"}]}
        return promote_regime_parameter_versions(
            self.db,
            validation_result=result,
            strategy_key=row.strategy_key,
            operator=operator,
            activate=False,
            source_validation_id=row.id,
        )

    def _existing_parameter_proposal(self, validation_id: int) -> bool:
        marker = f"source_validation_id={validation_id}"
        row = (
            self.db.execute(
                select(QuantParameterSet.id)
                .where(QuantParameterSet.status == "draft", QuantParameterSet.description.contains(marker))
                .limit(1)
            )
            .scalars()
            .first()
        )
        return row is not None
