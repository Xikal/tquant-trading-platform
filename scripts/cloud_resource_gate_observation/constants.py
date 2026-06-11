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

TRADING_DAY_CHECKPOINTS = (
    ("09:15", "pre-open baseline"),
    ("09:35", "after open pressure"),
    ("10:30", "sustained morning load"),
    ("11:30", "midday close"),
    ("13:05", "afternoon reopen"),
    ("14:55", "close pressure"),
    ("15:10", "post-close tasks"),
    ("15:30", "close-refresh cooldown"),
)

DEFAULT_THRESHOLDS = {
    "worker_memory_warning_pct": 85.0,
    "worker_memory_blocking_pct": 95.0,
    "swap_warning_pct": 35.0,
    "root_warning_pct": 75.0,
    "duplicate_success_warning_count": 12,
    "queue_warning_count": 1,
    "scheduler_provider_warning_blocking_lines": 20,
}
