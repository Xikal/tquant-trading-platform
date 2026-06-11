from __future__ import annotations

import json
from pathlib import Path

from app.services.tasks.registry import analytics_task_registry
from app.workers.runtime_worker import RUNTIME_WORKER_TASK_TYPES


ROOT = Path(__file__).resolve().parents[2]


def test_contract_first_toolchain_files_and_scripts_exist() -> None:
    package_json = json.loads((ROOT / "frontend-next" / "package.json").read_text(encoding="utf-8"))
    scripts = package_json["scripts"]

    assert (ROOT / "backend" / "scripts" / "export_openapi_schema.py").exists()
    assert (ROOT / "docs" / "contracts" / "openapi.json").exists()
    assert (ROOT / "frontend-next" / "src" / "generated" / "api-types.ts").exists()
    assert "openapi-typescript" in scripts["api:generate"]
    assert "npm run api:generate" in scripts["api:check"]
    assert "npm run typecheck" in scripts["api:check"]


def test_runtime_worker_keeps_critical_long_task_types() -> None:
    task_types = set(RUNTIME_WORKER_TASK_TYPES)

    assert {
        "daily_bar_refresh",
        "latest_data_watchdog",
        "a_key_level_materialization_refresh",
        "low_buy_materialization_refresh",
        "market_pulse_refresh",
        "market_quote_cache_refresh",
        "monitor_snapshot_refresh",
        "factor_mining_evaluate",
    }.issubset(task_types)


def test_analytics_registry_keeps_architecture_baseline_tasks() -> None:
    task_types = set(analytics_task_registry().task_types())

    assert {
        "data_backfill_24m",
        "analytics_export_daily_bars",
        "analytics_quality_check",
        "strategy_24m_duckdb_report",
        "backtest_all_strategies_24m",
        "data_quality_sla_refresh",
        "data_repair_run",
    }.issubset(task_types)
