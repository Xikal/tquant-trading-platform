from __future__ import annotations


HTTP_PATHS = (
    "/readyz",
    "/api/monitor",
    "/api/monitor/snapshot",
    "/api/priority-board",
    "/api/screeners/low-buy/priority-board",
    "/api/runtime-tasks/summary",
    "/next/monitor",
    "/next/monitor/market",
    "/next/strategy-tracking",
    "/next/analysis",
    "/next/backtest",
    "/next/data",
    "/next/settings",
)

CORE_PAGE_PATHS = (
    "/next/monitor",
    "/next/monitor/market",
    "/next/strategy-tracking",
    "/next/analysis",
    "/next/backtest",
    "/next/data",
    "/next/settings",
)

PROTECTED_API_PATHS = (
    "/api/monitor/snapshot",
    "/api/screeners/low-buy/priority-board",
    "/api/runtime-tasks/summary",
)

EXPECTED_CONTAINERS = {
    "tquant-app-mysql",
    "tquant-mysql",
    "tquant-redis",
    "tquant-runtime-worker-mysql",
    "tquant-runtime-scheduler-mysql",
}

CORE_DUPLICATE_TASK_TYPES = {
    "a_key_level_materialization_refresh",
    "strategy_tracking_snapshot_refresh",
}

LOW_PRIORITY_TASK_HINTS = (
    "analytics",
    "backtest",
    "ml",
    "factor",
    "data_repair",
    "research",
    "paper",
    "hermes_platform_autopilot",
)

DEFAULT_THRESHOLDS = {
    "worker_memory_warning_pct": 85.0,
    "worker_memory_blocking_pct": 95.0,
    "swap_warning_pct": 35.0,
    "root_warning_pct": 75.0,
    "duplicate_success_warning_count": 12,
    "queue_warning_count": 1,
}
