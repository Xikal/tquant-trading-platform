from __future__ import annotations

import logging
import socket
import time
from typing import Any

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.agent_daily_workflow_service import AgentDailyWorkflowService
from app.services.market.hourly_snapshot import HourlyAllMarketSnapshotService
from app.services.market_quote_cache_refresh import MarketQuoteCacheRefreshService
from app.services.monitor_snapshot_cache import build_and_store_monitor_snapshot
from app.services.tasks import RuntimeTaskQueue
from app.workers.latest_data_close_scheduler import (
    start_latest_data_close_scheduler,
    stop_latest_data_close_scheduler,
)
from app.workers.platform_autopilot_scheduler import (
    start_platform_autopilot_scheduler,
    stop_platform_autopilot_scheduler,
)

logger = logging.getLogger(__name__)


class RuntimeWorker:
    """Standalone runtime worker for non-request tasks."""

    def __init__(self, *, worker_id: str | None = None, poll_interval_seconds: float | None = None) -> None:
        settings = get_settings()
        self.worker_id = worker_id or f"runtime-{socket.gethostname()}"
        self.poll_interval_seconds = (
            poll_interval_seconds
            if poll_interval_seconds is not None
            else float(settings.runtime_worker_poll_interval_seconds)
        )

    def run_once(self) -> bool:
        with SessionLocal() as db:
            queue = RuntimeTaskQueue(db)
            task = queue.claim_next(worker_id=self.worker_id)
            if task is None:
                return False
            task_id = int(task.id)
            task_type = str(task.task_type)
            try:
                result = _execute_task(task_type, _json_payload(task.payload_json), db)
                queue.mark_succeeded(task_id, result)
            except Exception as exc:
                logger.exception("runtime task failed: id=%s type=%s", task_id, task_type)
                db.rollback()
                queue.mark_failed(task_id, str(exc), retryable=True)
            return True

    def run_forever(self) -> None:
        logger.info("runtime worker started: %s", self.worker_id)
        while True:
            did_work = self.run_once()
            if not did_work:
                time.sleep(self.poll_interval_seconds)


def _execute_task(task_type: str, payload: dict[str, Any], db) -> dict[str, Any]:  # noqa: ANN001
    if task_type == "noop":
        return {"ok": True, "message": "noop completed"}
    if task_type == "agent_daily_report_push":
        channel = str(payload.get("channel") or "feishu")
        response = AgentDailyWorkflowService().push_daily_report(db, channel=channel)
        return response.model_dump() if hasattr(response, "model_dump") else dict(response)
    if task_type == "monitor_snapshot_refresh":
        user_id = int(payload.get("user_id") or 0)
        priority_limit = int(payload.get("priority_limit") or 12)
        if user_id <= 0:
            raise ValueError("monitor snapshot refresh requires user_id")
        return build_and_store_monitor_snapshot(
            db,
            user_id=user_id,
            priority_limit=max(1, min(priority_limit, 30)),
        )
    if task_type == "market_quote_cache_refresh":
        return MarketQuoteCacheRefreshService(db).refresh(limit=int(payload.get("limit") or 200))
    if task_type == "market_hourly_all_a_snapshot":
        return HourlyAllMarketSnapshotService(db).refresh(
            reason=str(payload.get("reason") or "runtime_hourly_market_pulse")
        )
    if task_type == "instrument_sync":
        from app.services.instrument_sync_status import InstrumentSyncStatusService
        from app.services.market_data import MarketDataService

        kind = str(payload.get("kind") or "all")
        run_id = str(payload.get("run_id") or "")
        if not run_id:
            raise ValueError("instrument_sync requires run_id")
        status_service = InstrumentSyncStatusService()
        status_service.update(
            run_id=run_id,
            kind=kind,
            status="running",
            progress_pct=5.0,
            message="后台正在更新股票库",
        )

        def progress(progress_pct: float, message: str, result: dict[str, int] | None = None) -> None:
            status_service.update(
                run_id=run_id,
                kind=kind,
                status="running",
                progress_pct=progress_pct,
                message=message,
                result=result,
            )

        try:
            result = MarketDataService().sync_instruments(db, kind, progress_callback=progress)
        except Exception as exc:
            status_service.fail(run_id=run_id, kind=kind, error=str(exc)[:240] or "股票库更新失败")
            raise
        status_service.finish(run_id=run_id, kind=kind, result=result)
        return {"ok": True, "run_id": run_id, "result": result}
    if task_type == "daily_bar_refresh":
        from app.services.daily_bar_refresh import DailyBarRefreshService

        return DailyBarRefreshService(db).refresh_latest(limit=int(payload.get("limit") or 6000))
    if task_type in {"market_review_report", "paper_review_report"}:
        from app.services.market.review import MarketReviewService

        report = MarketReviewService(db).generate_review_report(
            report_slot=str(payload.get("report_slot") or "midday")
        )
        db.commit()
        return {
            "ok": True,
            "scope": "market",
            "report_id": report.id,
            "report_slot": report.report_slot,
            "report_date": report.report_date.isoformat() if report.report_date else "",
        }
    if task_type == "low_buy_materialization_refresh":
        from app.services.low_buy_materialization import refresh_latest_low_buy_materialization

        return refresh_latest_low_buy_materialization(
            limit=int(payload.get("limit") or 40),
            scan_limit=int(payload.get("scan_limit") or 480),
        )
    if task_type == "ml_signal_incremental_train":
        from app.models.schema_defs.phase4 import MLSignalIncrementalTrainRequest
        from app.services.ml_signal import MLSignalService

        response = MLSignalService(db).incremental_train(
            MLSignalIncrementalTrainRequest(
                model_key=str(payload.get("model_key") or ""),
                model_type=str(payload.get("model_type") or "xgboost"),  # type: ignore[arg-type]
                source="paper",
                limit=int(payload.get("limit") or 5000),
                min_samples=int(payload.get("min_samples") or 100),
                validation_ratio=float(payload.get("validation_ratio") or 0.2),
                promote=bool(payload.get("promote") if "promote" in payload else False),
                warm_start=bool(payload.get("warm_start") if "warm_start" in payload else True),
                max_validation_p_value=float(payload.get("max_validation_p_value") or 0.05),
                min_validation_accuracy=float(payload.get("min_validation_accuracy") or 0.55),
            )
        )
        return response.model_dump() if hasattr(response, "model_dump") else dict(response)
    if task_type == "strategy_self_evolution":
        from app.services.strategy_self_evolution import StrategySelfEvolutionOrchestrator

        return StrategySelfEvolutionOrchestrator(db).run(payload)
    if task_type == "ml_feature_drift_monitor":
        from app.services.strategy_self_evolution import StrategySelfEvolutionOrchestrator

        return StrategySelfEvolutionOrchestrator(db).run_drift_monitor(payload)
    if task_type == "paper_ledger_reconcile_preview":
        from app.services.paper.ledger_reconcile_monitor import PaperLedgerReconcileMonitorService

        return PaperLedgerReconcileMonitorService(db).run_daily_preview(
            threshold=float(payload.get("threshold") or 1.0),
            channel=str(payload.get("channel") or "feishu"),
        )
    if task_type == "hermes_platform_autopilot":
        from app.services.platform_autopilot import PlatformAutopilotService

        response = PlatformAutopilotService(db).run(
            auto_repair=bool(payload.get("auto_repair", True)),
            notify=bool(payload.get("notify", True)),
            trigger=str(payload.get("trigger") or "scheduled"),
        )
        return response.model_dump(mode="json")
    if task_type == "factor_mining_evaluate":
        from app.models.schema_defs.factor_mining import FactorEvaluationRequest
        from app.services.factor_mining.orchestrator import FactorMiningOrchestrator

        factor_key = str(payload.get("factor_key") or "")
        if not factor_key:
            raise ValueError("factor_mining_evaluate requires factor_key")
        response = FactorMiningOrchestrator(db).evaluate_factor(
            factor_key,
            FactorEvaluationRequest.model_validate(payload.get("evaluation") or payload),
        )
        return response.model_dump(mode="json")
    if task_type == "factor_mining_monthly":
        from app.services.factor_mining.hypothesis_agent import FactorHypothesisAgent

        response = FactorHypothesisAgent(db).generate(
            topic=str(payload.get("topic") or "A股低吸因子挖掘"),
            count=int(payload.get("count") or 20),
            use_llm=True,
        )
        return response.model_dump(mode="json")
    raise ValueError(f"未知任务类型: {task_type}")


def _json_payload(raw: str) -> dict[str, Any]:
    import json

    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    start_latest_data_close_scheduler()
    start_platform_autopilot_scheduler()
    try:
        RuntimeWorker().run_forever()
    finally:
        stop_platform_autopilot_scheduler()
        stop_latest_data_close_scheduler()


if __name__ == "__main__":
    main()
