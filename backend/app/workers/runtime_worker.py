from __future__ import annotations

import logging
import socket
import time
from typing import Any

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.agent_daily_workflow_service import AgentDailyWorkflowService
from app.services.market_quote_cache_refresh import MarketQuoteCacheRefreshService
from app.services.monitor_snapshot_cache import build_and_store_monitor_snapshot
from app.services.tasks import RuntimeTaskQueue

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
    if task_type == "daily_bar_refresh":
        from app.services.daily_bar_refresh import DailyBarRefreshService

        return DailyBarRefreshService(db).refresh_latest(limit=int(payload.get("limit") or 6000))
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
                promote=bool(payload.get("promote") if "promote" in payload else True),
                warm_start=bool(payload.get("warm_start") if "warm_start" in payload else True),
                max_validation_p_value=float(payload.get("max_validation_p_value") or 0.05),
                min_validation_accuracy=float(payload.get("min_validation_accuracy") or 0.55),
            )
        )
        return response.model_dump() if hasattr(response, "model_dump") else dict(response)
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
    RuntimeWorker().run_forever()


if __name__ == "__main__":
    main()
