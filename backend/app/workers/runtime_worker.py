from __future__ import annotations

import logging
import os
from pathlib import Path
import socket
import sys
import threading
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
from app.services.tasks.registry import task_definitions_for_worker
from app.runtime.background_jobs import (
    shutdown_runtime_background_jobs,
    start_runtime_background_jobs,
)
from app.workers.heavy_research_tasks import (
    FACTOR_HEAVY_TASK_TYPES,
    HEAVY_RESEARCH_TASK_TYPES,
    ML_HEAVY_TASK_TYPES,
    execute_heavy_research_task,
)
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
    *task_definitions_for_worker("runtime"),
)
RESEARCH_TASK_TYPES = {
    *HEAVY_RESEARCH_TASK_TYPES,
    "ml_signal_incremental_train",
    "ml_feature_drift_monitor",
    "factor_mining_evaluate",
    "factor_mining_monthly",
    "trading_experience_review_refresh",
    "trading_experience_tag_materialization",
    "trading_experience_relative_strength_refresh",
    "trading_experience_limit_up_backtest",
}
ML_TASK_TYPES = {"ml_signal_incremental_train", "ml_feature_drift_monitor", *ML_HEAVY_TASK_TYPES}
FACTOR_TASK_TYPES = {"factor_mining_evaluate", "factor_mining_monthly", *FACTOR_HEAVY_TASK_TYPES}
PAPER_TASK_TYPES = {
    "paper_review_report",
    "paper_portfolio_execution_preview",
    "paper_ledger_reconcile_preview",
}
RUNTIME_WORKER_CLAIM_TASK_TYPES = tuple(sorted({*RUNTIME_WORKER_TASK_TYPES, *PAPER_TASK_TYPES}))
LONG_TASK_HEARTBEAT_SECONDS = 30.0


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
            _record_worker_heartbeat(db, worker_id=self.worker_id)
            queue = RuntimeTaskQueue(db)
            task = queue.claim_next(worker_id=self.worker_id, task_types=RUNTIME_WORKER_CLAIM_TASK_TYPES)
            if task is None:
                return False
            task_id = int(task.id)
            task_type = str(task.task_type)
            heartbeat_stop = threading.Event()
            heartbeat_thread = _start_task_heartbeat(worker_id=self.worker_id, stop_event=heartbeat_stop)
            try:
                queue.update_progress(
                    task_id,
                    progress_pct=5.0,
                    message="任务已被 Runtime Worker 接收",
                    payload={"worker_id": self.worker_id, "task_type": task_type},
                )
                if is_removed_paper_task(task_type):
                    queue.mark_skipped(
                        task_id,
                        f"{task_type} skipped: paper trading feature has been removed",
                        result=removed_paper_task_result(task_type),
                    )
                else:
                    result = _execute_task(task_type, _json_payload(task.payload_json), db)
                    queue.update_progress(
                        task_id,
                        progress_pct=95.0,
                        message="任务计算完成，准备写入结果",
                        payload={"worker_id": self.worker_id, "task_type": task_type},
                    )
                    queue.mark_succeeded(task_id, result)
            except Exception as exc:
                logger.exception("runtime task failed: id=%s type=%s", task_id, task_type)
                db.rollback()
                queue.mark_failed(task_id, str(exc), retryable=True)
            finally:
                heartbeat_stop.set()
                heartbeat_thread.join(timeout=1.0)
            _record_worker_heartbeat(db, worker_id=self.worker_id)
            return True

    def run_forever(self) -> None:
        logger.info("runtime worker started: %s", self.worker_id)
        while True:
            did_work = self.run_once()
            if did_work and _should_recycle_after_task():
                logger.warning("runtime worker recycling after task: worker_id=%s", self.worker_id)
                raise SystemExit(0)
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
        return MarketQuoteCacheRefreshService(db).refresh(
            limit=int(payload.get("limit") or 200),
            demand_warmup=bool(payload.get("demand_warmup", True)),
        )
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

        result = DailyBarRefreshService(db).refresh_latest(
            limit=int(payload.get("limit") or 6000),
            expected_trade_date=str(payload.get("expected_trade_date") or "") or None,
        )
        if result.get("ok"):
            from app.services.latest_data_close_refresh import enqueue_latest_data_close_refresh
            from app.services.latest_data_watchdog import LatestDailyBarWatchdog
            from app.services.low_buy_materialization import enqueue_low_buy_materialization

            result["next_refresh_check"] = enqueue_latest_data_close_refresh(db)
            enqueue_low_buy_materialization(db, reason="daily_bar_refresh_success_priority_board_read_model", commit=True)
            result["priority_board_read_model_refresh_queued"] = True
            result["post_close_notification"] = LatestDailyBarWatchdog().run(
                db,
                trade_date=str(result.get("trade_date") or payload.get("expected_trade_date") or "") or None,
                notify=True,
                enforce_watchdog_time_gate=False,
            )
        return result
    if task_type == "latest_data_watchdog":
        from app.services.latest_data_watchdog import LatestDailyBarWatchdog

        result = LatestDailyBarWatchdog().run(
            db,
            trade_date=str(payload.get("expected_trade_date") or payload.get("trade_date") or "") or None,
            notify=bool(payload.get("notify", True)),
            force_notify=bool(payload.get("force_notify", False)),
            enforce_watchdog_time_gate=bool(payload.get("enforce_watchdog_time_gate", True)),
        )
        if result.get("ok"):
            from app.services.latest_data_close_refresh import enqueue_after_close_followups

            trade_date = str(
                result.get("trade_date")
                or result.get("expected_trade_date")
                or payload.get("expected_trade_date")
                or payload.get("trade_date")
                or ""
            )
            if trade_date:
                result["after_close_followups"] = enqueue_after_close_followups(
                    db,
                    trade_date=trade_date,
                    reason="latest_data_watchdog_ok",
                )
        return result
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
    if task_type == "market_review_report":
        from app.services.market.review import MarketReviewService

        target_date = _payload_date(payload, "target_date")
        report = MarketReviewService(db).generate_review_report(
            report_slot=str(payload.get("report_slot") or "midday"),
            target_date=target_date,
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
        from app.services.low_buy_materialization import (
            refresh_latest_low_buy_materialization,
            refresh_low_buy_close_review_snapshots,
        )

        strategies = [str(item) for item in payload.get("strategies") or []] or None

        result = refresh_latest_low_buy_materialization(
            limit=int(payload.get("limit") or 40),
            scan_limit=int(payload.get("scan_limit") or 480),
            strategies=strategies,
        )
        _ensure_low_buy_materialization_complete(result)
        if payload.get("build_close_review"):
            trade_date = str(
                payload.get("expected_trade_date")
                or result.get("published_trade_date")
                or (result.get("publish_status") or {}).get("published_trade_date")
                or ""
            )
            result["close_review_snapshots"] = refresh_low_buy_close_review_snapshots(
                strategies=strategies or [],
                trade_date=trade_date,
            )
            if result["close_review_snapshots"].get("ok") is False:
                skipped = result["close_review_snapshots"].get("skipped") or []
                raise RuntimeError(f"low-buy close review refresh incomplete: {skipped}")
        return result
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
    if task_type in HEAVY_RESEARCH_TASK_TYPES:
        return execute_heavy_research_task(task_type, payload, db)
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
    if task_type == "ml_feature_drift_monitor":
        from app.services.strategy_self_evolution import StrategySelfEvolutionOrchestrator

        return StrategySelfEvolutionOrchestrator(db).run_drift_monitor(payload)
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
    if task_type in {
        "trading_experience_review_refresh",
        "trading_experience_tag_materialization",
        "trading_experience_relative_strength_refresh",
        "trading_experience_limit_up_backtest",
    }:
        return _execute_trading_experience_task(task_type, payload, db)
    raise ValueError(f"未知任务类型: {task_type}")


def _ensure_task_enabled(task_type: str) -> None:
    settings = get_settings()
    if is_removed_paper_task(task_type):
        raise RuntimeError(f"{task_type} is disabled: paper trading feature has been removed")
    if task_type in RESEARCH_TASK_TYPES and not settings.tquant_research_jobs_enabled:
        raise RuntimeError(f"{task_type} is disabled: set TQUANT_RESEARCH_JOBS_ENABLED=true")
    if task_type in ML_TASK_TYPES and not settings.tquant_ml_jobs_enabled:
        raise RuntimeError(f"{task_type} is disabled: set TQUANT_ML_JOBS_ENABLED=true")
    if task_type in FACTOR_TASK_TYPES and not settings.tquant_factor_jobs_enabled:
        raise RuntimeError(f"{task_type} is disabled: set TQUANT_FACTOR_JOBS_ENABLED=true")


def _current_rss_mb() -> float | None:
    if sys.platform.startswith("linux"):
        try:
            pages = int(Path("/proc/self/statm").read_text(encoding="utf-8").split()[1])
        except (OSError, IndexError, ValueError):
            return None
        page_size = os.sysconf("SC_PAGE_SIZE")
        return pages * page_size / (1024 * 1024)
    try:
        import resource
    except ImportError:
        return None
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if usage <= 0:
        return None
    # macOS reports bytes, Linux reports KiB. Linux is handled above.
    return usage / (1024 * 1024)


def _should_recycle_after_task() -> bool:
    threshold_mb = int(getattr(get_settings(), "runtime_worker_recycle_rss_mb", 0) or 0)
    if threshold_mb <= 0:
        return False
    rss_mb = _current_rss_mb()
    if rss_mb is None:
        logger.warning("runtime worker recycle threshold configured but rss is unavailable")
        return False
    if rss_mb < float(threshold_mb):
        return False
    logger.warning(
        "runtime worker rss %.1fMiB reached recycle threshold %sMiB after task",
        rss_mb,
        threshold_mb,
    )
    return True


def is_removed_paper_task(task_type: str) -> bool:
    normalized = str(task_type or "").strip()
    return normalized in PAPER_TASK_TYPES or normalized.startswith("paper_")


def removed_paper_task_result(task_type: str) -> dict[str, Any]:
    return {
        "ok": True,
        "skipped": True,
        "reason": "removed_feature",
        "feature": "paper_trading",
        "task_type": str(task_type or ""),
        "status": "skipped_removed_feature",
    }


def _json_payload(raw: str) -> dict[str, Any]:
    import json

    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _payload_date(payload: dict[str, Any], key: str) -> date | None:
    raw = str(payload.get(key) or "").strip()
    if not raw:
        return None
    return date.fromisoformat(raw[:10])


def _record_worker_heartbeat(db, *, worker_id: str) -> None:  # noqa: ANN001
    try:
        from app.services.runtime_worker_health import record_runtime_worker_heartbeat

        record_runtime_worker_heartbeat(db, worker_id=worker_id)
    except Exception:
        logger.exception("runtime worker heartbeat update failed: worker_id=%s", worker_id)


def _start_task_heartbeat(*, worker_id: str, stop_event: threading.Event) -> threading.Thread:
    def _loop() -> None:
        while not stop_event.wait(LONG_TASK_HEARTBEAT_SECONDS):
            with SessionLocal() as heartbeat_db:
                _record_worker_heartbeat(heartbeat_db, worker_id=worker_id)

    thread = threading.Thread(target=_loop, name=f"runtime-heartbeat-{worker_id}", daemon=True)
    thread.start()
    return thread


def _ensure_low_buy_materialization_complete(result: dict[str, Any]) -> None:
    if result.get("ok") is not True:
        missing_required = result.get("missing_required_strategies") or result.get("missing_strategies") or []
        skipped_strategies = result.get("skipped_strategies") or []
        skipped = result.get("skipped") or []
        raise RuntimeError(
            "low_buy_materialization_refresh incomplete: "
            f"missing_required_strategies={missing_required}; "
            f"skipped_strategies={skipped_strategies}; skipped={skipped}"
        )
    priority_board = result.get("priority_board_read_models") or {}
    if isinstance(priority_board, dict) and priority_board.get("ok") is False:
        raise RuntimeError(
            "low_buy_materialization_refresh priority board warmup incomplete: "
            f"skipped={priority_board.get('skipped') or []}"
        )


def _execute_trading_experience_task(task_type: str, payload: dict[str, Any], db) -> dict[str, Any]:  # noqa: ANN001
    from datetime import date as date_type

    from app.services.trading_experience import limit_up_followthrough, review_pool
    from app.services.trading_experience.service import TradingExperienceService

    raw_date = str(payload.get("trade_date") or "")
    trade_date = date_type.fromisoformat(raw_date) if raw_date else None
    service = TradingExperienceService(db)
    if task_type == "trading_experience_review_refresh":
        items = review_pool.build_review_pool(db, pool_date=trade_date, limit=int(payload.get("limit") or 50), persist=True)
        return {"ok": True, "item_count": len(items), "data_quality": "ok" if items else "insufficient"}
    if task_type == "trading_experience_tag_materialization":
        symbol = str(payload.get("symbol") or "")
        if not symbol:
            return {"ok": True, "status": "blocked", "reason": "symbol_required"}
        response = service.volume_position_tags(symbol, trade_date=trade_date)
        return response.model_dump(mode="json")
    if task_type == "trading_experience_relative_strength_refresh":
        response = service.relative_strength(trade_date=trade_date, limit=int(payload.get("limit") or 50))
        return response.model_dump(mode="json")
    if task_type == "trading_experience_limit_up_backtest":
        report = limit_up_followthrough.build_backtest_report(db, end_date=trade_date)
        limit_up_followthrough.persist_backtest_report(db, report)
        return report
    raise ValueError(f"未知任务类型: {task_type}")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    embedded_scheduler_started = False
    start_latest_data_close_scheduler()
    if settings.platform_autopilot_enabled:
        start_platform_autopilot_scheduler()
    if settings.runtime_worker_embed_scheduler:
        start_runtime_background_jobs()
        embedded_scheduler_started = True
    try:
        RuntimeWorker().run_forever()
    finally:
        if embedded_scheduler_started:
            shutdown_runtime_background_jobs()
        if settings.platform_autopilot_enabled:
            stop_platform_autopilot_scheduler()
        stop_latest_data_close_scheduler()


if __name__ == "__main__":
    main()
