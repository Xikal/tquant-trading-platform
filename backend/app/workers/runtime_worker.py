from __future__ import annotations

import logging
import socket
import time
from datetime import date
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

RUNTIME_WORKER_TASK_TYPES = (
    "noop",
    "agent_daily_report_push",
    "monitor_snapshot_refresh",
    "market_quote_cache_refresh",
    "market_hourly_all_a_snapshot",
    "market_pulse_refresh",
    "instrument_sync",
    "daily_bar_refresh",
    "a_key_level_materialization_refresh",
    "market_review_report",
    "paper_review_report",
    "low_buy_materialization_refresh",
    "market_state_gate_refresh",
    "sector_leader_snapshot_refresh",
    "hard_risk_context_refresh",
    "signal_attribution_refresh",
    "intraday_entry_snapshot_refresh",
    "event_risk_refresh",
    "strategy_promotion_review",
    "paper_portfolio_execution_preview",
    "strategy_tracking_snapshot_refresh",
    "ml_signal_incremental_train",
    "strategy_self_evolution",
    "ml_feature_drift_monitor",
    "paper_ledger_reconcile_preview",
    "hermes_platform_autopilot",
    "signal_ledger_capture",
    "factor_mining_evaluate",
    "factor_mining_monthly",
)
RESEARCH_TASK_TYPES = {
    "ml_signal_incremental_train",
    "strategy_self_evolution",
    "ml_feature_drift_monitor",
    "factor_mining_evaluate",
    "factor_mining_monthly",
}
ML_TASK_TYPES = {"ml_signal_incremental_train", "strategy_self_evolution", "ml_feature_drift_monitor"}
FACTOR_TASK_TYPES = {"factor_mining_evaluate", "factor_mining_monthly"}


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
            task = queue.claim_next(worker_id=self.worker_id, task_types=RUNTIME_WORKER_TASK_TYPES)
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
    _ensure_task_enabled(task_type)
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
    if task_type == "market_pulse_refresh":
        from app.api.routes.market import refresh_market_pulse_snapshot
        from app.services.market.pulse_history import record_market_pulse_event

        pulse = refresh_market_pulse_snapshot(db)
        record_market_pulse_event(db, pulse)
        db.commit()
        return {"ok": True, "data_quality": str(pulse.data_quality), "pulse_level": pulse.pulse_level}
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
    if task_type == "a_key_level_materialization_refresh":
        from app.services.key_levels.materialization import AKeyLevelMaterializationService

        return AKeyLevelMaterializationService(db).refresh(
            trade_date=str(payload.get("trade_date") or "") or None,
            symbols=[str(item) for item in payload.get("symbols") or []] if "symbols" in payload else None,
            sectors=[str(item) for item in payload.get("sectors") or []] if "sectors" in payload else None,
            stock_limit=max(1, min(int(payload["stock_limit"]), 10000)) if payload.get("stock_limit") else None,
            sector_limit=max(1, min(int(payload["sector_limit"]), 1000)) if payload.get("sector_limit") else None,
            batch_size=max(1, min(int(payload["batch_size"]), 1000)) if payload.get("batch_size") else 250,
        )
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
            strategies=[str(item) for item in payload.get("strategies") or []] or None,
        )
    if task_type == "market_state_gate_refresh":
        from app.services.decision_context.market_gate import market_gate_from_context
        from app.services.low_buy.priority_market import empty_priority_market_context

        gate = market_gate_from_context(empty_priority_market_context())
        return {"ok": True, "gate": gate.model_dump(mode="json"), "worker_scope": "runtime-worker"}
    if task_type == "hard_risk_context_refresh":
        return {
            "ok": True,
            "worker_scope": "runtime-worker",
            "message": "hard risk context refresh uses synchronous signal snapshots in Batch A",
        }
    if task_type == "sector_leader_snapshot_refresh":
        from app.services.decision_context.sector_leader_gate import enrich_sector_relative_strength_response
        from app.services.market_data import MarketDataService

        response = MarketDataService().sector_relative_strength_rank(
            db,
            limit=max(1, min(int(payload.get("limit") or 8), 20)),
            per_sector_limit=max(1, min(int(payload.get("per_sector_limit") or 10), 30)),
        )
        enriched = enrich_sector_relative_strength_response(response)
        return {
            "ok": True,
            "worker_scope": "runtime-worker",
            "task_type": task_type,
            "gate_owner": "production-traceability",
            "not_research_gated": True,
            "item_count": len(enriched.items or []),
            "snapshot": enriched.model_dump(mode="json"),
        }
    if task_type == "strategy_promotion_review":
        from app.services.decision_context.promotion_engine import PromotionEvidence, review_strategy_promotion

        strategy_key = str(payload.get("strategy_key") or "").strip()
        required_fields = {
            "sample_count",
            "profit_factor",
            "average_trade_pct",
            "max_drawdown_pct",
            "max5_return_pct",
            "max10_return_pct",
            "quarterly_stability",
            "walk_forward_pass",
            "oos_pass",
        }
        missing = sorted(field for field in required_fields if field not in payload)
        if not strategy_key or missing:
            return {
                "ok": False,
                "status": "blocked_by_data",
                "worker_scope": "runtime-worker",
                "reason": "strategy_promotion_review requires explicit promotion evidence payload",
                "missing_fields": (["strategy_key"] if not strategy_key else []) + missing,
            }
        evidence = PromotionEvidence(
            strategy_key=strategy_key,
            review_date=date.fromisoformat(str(payload.get("review_date") or date.today().isoformat())[:10]),
            window_days=int(payload.get("window_days") or 504),
            sample_count=int(payload.get("sample_count") or 0),
            profit_factor=float(payload.get("profit_factor") or 0.0),
            average_trade_pct=float(payload.get("average_trade_pct") or 0.0),
            max_drawdown_pct=float(payload.get("max_drawdown_pct") or 0.0),
            max5_return_pct=float(payload.get("max5_return_pct") or 0.0),
            max10_return_pct=float(payload.get("max10_return_pct") or 0.0),
            quarterly_stability=float(payload.get("quarterly_stability") or 0.0),
            walk_forward_pass=bool(payload.get("walk_forward_pass")),
            oos_pass=bool(payload.get("oos_pass")),
            recent_quarter_returns_pct=tuple(float(item) for item in payload.get("recent_quarter_returns_pct") or []),
            source=str(payload.get("source") or "runtime_task_payload"),
        )
        result = review_strategy_promotion(db, evidence)
        return {
            "ok": True,
            "worker_scope": "runtime-worker",
            "task_type": task_type,
            "gate_owner": "advisory-only",
            "auto_apply_enabled": False,
            "review": result.as_payload(),
        }
    if task_type == "paper_portfolio_execution_preview":
        from app.services.paper.performance import PaperPerformanceService

        account_id = int(payload.get("account_id") or 0)
        if account_id <= 0:
            return {
                "ok": False,
                "status": "blocked_by_data",
                "worker_scope": "runtime-worker",
                "reason": "paper_portfolio_execution_preview requires account_id",
            }
        return {
            "ok": True,
            "worker_scope": "runtime-worker",
            "task_type": task_type,
            "preview": PaperPerformanceService(db).compute_portfolio_execution_preview(account_id),
        }
    if task_type == "signal_attribution_refresh":
        from app.services.decision_context.signal_attribution import refresh_signal_attributions

        return refresh_signal_attributions(
            db,
            as_of_date=date.fromisoformat(str(payload.get("as_of_date") or date.today().isoformat())[:10]),
            horizons=[int(item) for item in payload.get("horizons") or [1, 3, 5, 10]],
            limit=max(1, min(int(payload.get("limit") or 200), 1000)),
        )
    if task_type == "intraday_entry_snapshot_refresh":
        from app.services.decision_context.intraday_entry import refresh_intraday_entry_snapshots

        return refresh_intraday_entry_snapshots(
            db,
            symbols=[str(item) for item in payload.get("symbols") or []],
            trade_date=date.fromisoformat(str(payload.get("trade_date") or date.today().isoformat())[:10]),
            entry_context=payload.get("entry_context") if isinstance(payload.get("entry_context"), dict) else {},
            bar_period=str(payload.get("bar_period") or "1m"),
            limit=max(5, min(int(payload.get("limit") or 120), 240)),
        )
    if task_type == "event_risk_refresh":
        from app.services.decision_context.event_risk import refresh_event_risk

        return refresh_event_risk(
            db,
            symbols=[str(item) for item in payload.get("symbols") or []],
            trade_date=date.fromisoformat(str(payload.get("trade_date") or date.today().isoformat())[:10]),
            limit_per_symbol=max(1, min(int(payload.get("limit_per_symbol") or 8), 20)),
        )
    if task_type == "strategy_tracking_snapshot_refresh":
        from app.services.strategy_tracking_snapshot import StrategyTrackingSnapshotBuilder

        response = StrategyTrackingSnapshotBuilder(db).rebuild_snapshot(
            range_days=int(payload.get("range_days") or payload.get("range") or 30),
            strategy_key=str(payload.get("strategy_key") or "") or None,
            strategy_family=str(payload.get("strategy_family") or "") or None,
        )
        return response.model_dump(mode="json")
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
    if task_type == "signal_ledger_capture":
        from app.services.track_record.signal_ledger import capture_latest_priority_board

        result = capture_latest_priority_board(
            db,
            as_of=date.fromisoformat(str(payload.get("as_of_date") or date.today().isoformat())[:10]),
            limit=max(1, min(int(payload.get("limit") or 30), 100)),
        )
        return {
            **result,
            "worker_scope": "runtime-worker",
            "task_type": task_type,
            "gate_owner": "production-track-record",
            "not_research_gated": True,
        }
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


def _ensure_task_enabled(task_type: str) -> None:
    settings = get_settings()
    if task_type in RESEARCH_TASK_TYPES and not settings.tquant_research_jobs_enabled:
        raise RuntimeError(f"{task_type} is disabled: set TQUANT_RESEARCH_JOBS_ENABLED=true")
    if task_type in ML_TASK_TYPES and not settings.tquant_ml_jobs_enabled:
        raise RuntimeError(f"{task_type} is disabled: set TQUANT_ML_JOBS_ENABLED=true")
    if task_type in FACTOR_TASK_TYPES and not settings.tquant_factor_jobs_enabled:
        raise RuntimeError(f"{task_type} is disabled: set TQUANT_FACTOR_JOBS_ENABLED=true")


def _json_payload(raw: str) -> dict[str, Any]:
    import json

    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    start_latest_data_close_scheduler()
    if settings.platform_autopilot_enabled:
        start_platform_autopilot_scheduler()
    try:
        RuntimeWorker().run_forever()
    finally:
        if settings.platform_autopilot_enabled:
            stop_platform_autopilot_scheduler()
        stop_latest_data_close_scheduler()


if __name__ == "__main__":
    main()
