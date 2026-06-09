from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.tasks.handlers import RegisteredHandler


@dataclass(frozen=True)
class TaskDefinition:
    task_type: str
    owner_role: str
    worker: str
    retry_policy: str
    max_attempts: int
    artifact_kind: str
    idempotency_required: bool
    expected_runtime_p95_ms: int


RUNTIME_TASK_TYPES: tuple[str, ...] = (
    "noop",
    "agent_daily_report_push",
    "monitor_snapshot_refresh",
    "market_quote_cache_refresh",
    "market_hourly_all_a_snapshot",
    "market_pulse_refresh",
    "instrument_sync",
    "daily_bar_refresh",
    "latest_data_watchdog",
    "a_key_level_materialization_refresh",
    "market_review_report",
    "low_buy_materialization_refresh",
    "market_state_gate_refresh",
    "sector_leader_snapshot_refresh",
    "hard_risk_context_refresh",
    "signal_attribution_refresh",
    "intraday_entry_snapshot_refresh",
    "event_risk_refresh",
    "strategy_promotion_review",
    "strategy_tracking_snapshot_refresh",
    "low_buy_execution_backtest",
    "legacy_research_backtest",
    "etf_t0_minute_backtest",
    "etf_t0_research_report",
    "backtest_portfolio_optimization",
    "backtest_position_policy_research",
    "ml_signal_build_samples",
    "ml_signal_train",
    "factor_mining_iterate",
    "analysis_batch",
    "ml_signal_incremental_train",
    "ml_feature_drift_monitor",
    "hermes_platform_autopilot",
    "signal_ledger_capture",
    "factor_mining_evaluate",
    "factor_mining_monthly",
    "trading_experience_review_refresh",
    "trading_experience_tag_materialization",
    "trading_experience_relative_strength_refresh",
    "trading_experience_limit_up_backtest",
)

ANALYTICS_TASK_TYPES: tuple[str, ...] = (
    "data_backfill_24m",
    "data_quality_backfill",
    "analytics_export_daily_bars",
    "analytics_export_key_level_snapshots",
    "analytics_export_low_buy_result_snapshots",
    "analytics_export_strategy_tracking_snapshots",
    "analytics_export_backtest_runs",
    "analytics_export_backtest_trades",
    "analytics_export_backtest_daily_snapshots",
    "analytics_export_analysis_logs",
    "analytics_export_market_review_reports",
    "analytics_quality_check",
    "strategy_24m_duckdb_report",
    "decision_context_24m_report",
    "portfolio_execution_24m_report",
    "backtest_all_strategies_24m",
    "data_quality_sla_refresh",
    "data_repair_run",
    "realized_outcome_refresh",
    "strategy_drift_refresh",
)


def task_definition(
    task_type: str,
    *,
    worker: str,
    owner_role: str | None = None,
    retry_policy: str = "queue_backoff",
    max_attempts: int = 2,
    artifact_kind: str | None = None,
    idempotency_required: bool | None = None,
    expected_runtime_p95_ms: int | None = None,
) -> TaskDefinition:
    return TaskDefinition(
        task_type=task_type,
        owner_role=owner_role or _infer_owner_role(task_type),
        worker=worker,
        retry_policy=retry_policy,
        max_attempts=max_attempts,
        artifact_kind=artifact_kind or _infer_artifact_kind(task_type),
        idempotency_required=_infer_idempotency_required(task_type)
        if idempotency_required is None
        else bool(idempotency_required),
        expected_runtime_p95_ms=expected_runtime_p95_ms
        if expected_runtime_p95_ms is not None
        else (1_800_000 if worker == "analytics" else 300_000),
    )


class TaskHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, RegisteredHandler] = {}

    def register(self, task_type: str, handler: RegisteredHandler) -> None:
        key = str(task_type).strip()
        if not key:
            raise ValueError("task_type is required")
        self._handlers[key] = handler

    def get(self, task_type: str) -> RegisteredHandler:
        try:
            return self._handlers[task_type]
        except KeyError as exc:
            raise ValueError(f"未知任务类型: {task_type}") from exc

    def task_types(self) -> list[str]:
        return sorted(self._handlers)


def analytics_task_registry() -> TaskHandlerRegistry:
    from app.services.tasks.analytics_handlers import register_analytics_handlers

    registry = TaskHandlerRegistry()
    register_analytics_handlers(registry)
    return registry


def _infer_owner_role(task_type: str) -> str:
    if any(token in task_type for token in ("data", "market", "instrument", "daily_bar", "key_level")):
        return "data"
    if any(
        token in task_type
        for token in (
            "strategy",
            "low_buy",
            "backtest",
            "factor",
            "ml",
            "research",
            "analysis",
            "paper",
            "signal",
            "trading_experience",
            "portfolio",
        )
    ):
        return "quant"
    return "devops"


def _infer_artifact_kind(task_type: str) -> str:
    if "export" in task_type:
        return "parquet"
    if "report" in task_type or "backtest" in task_type:
        return "report"
    if "snapshot" in task_type or "materialization" in task_type:
        return "snapshot"
    if any(token in task_type for token in ("refresh", "watchdog", "quality", "repair", "drift")):
        return "metrics"
    return "none"


def _infer_idempotency_required(task_type: str) -> bool:
    return any(
        token in task_type
        for token in (
            "refresh",
            "watchdog",
            "snapshot",
            "materialization",
            "report",
            "sync",
            "backtest",
            "export",
            "quality",
            "repair",
        )
    )


RUNTIME_TASK_REGISTRY: dict[str, TaskDefinition] = {
    **{task_type: task_definition(task_type, worker="runtime") for task_type in RUNTIME_TASK_TYPES},
    **{task_type: task_definition(task_type, worker="analytics") for task_type in ANALYTICS_TASK_TYPES},
}


def task_definitions_for_worker(worker: str) -> dict[str, TaskDefinition]:
    return {
        task_type: definition
        for task_type, definition in RUNTIME_TASK_REGISTRY.items()
        if definition.worker == worker
    }
