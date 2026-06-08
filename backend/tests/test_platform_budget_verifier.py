from __future__ import annotations

import json
import runpy
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "scripts" / "verify_platform_budget.py"


def run_budget_report(fixture: dict[str, object], tmp_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    fixture_path = tmp_path / "fixture.json"
    report_path = tmp_path / "budget.json"
    markdown_path = tmp_path / "budget.md"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--fixture",
            str(fixture_path),
            "--json-output",
            str(report_path),
            "--markdown-output",
            str(markdown_path),
            *extra,
        ],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )


def sample_budget_report(**overrides: object) -> dict[str, object]:
    roles = {
        "web": {
            "container": "tquant-app-mysql",
            "container_present": True,
            "env": {
                "DB_POOL_SIZE": "4",
                "DB_MAX_OVERFLOW": "4",
                "RUNTIME_BACKGROUND_ROLE": "web",
                "RUNTIME_BACKGROUND_JOBS_ENABLED": "false",
                "TQUANT_ANALYTICS_ENABLED": "false",
                "APP_WORKERS": "2",
            },
            "pool_budget": 8,
        },
        "runtime_worker": {
            "container": "tquant-runtime-worker-mysql",
            "container_present": True,
            "env": {
                "DB_POOL_SIZE": "2",
                "DB_MAX_OVERFLOW": "2",
                "RUNTIME_BACKGROUND_ROLE": "worker",
                "RUNTIME_LOW_PRIORITY_TASKS_PAUSED": "true",
            },
            "pool_budget": 4,
        },
        "runtime_scheduler": {
            "container": "tquant-runtime-scheduler-mysql",
            "container_present": True,
            "env": {
                "DB_POOL_SIZE": "2",
                "DB_MAX_OVERFLOW": "2",
                "RUNTIME_BACKGROUND_ROLE": "scheduler",
                "RUNTIME_BACKGROUND_COMPACT_MODE_ENABLED": "true",
                "RUNTIME_QUOTE_CACHE_REFRESH_INTERVAL_SECONDS": "180",
                "RUNTIME_LOW_PRIORITY_TASKS_PAUSED": "true",
            },
            "pool_budget": 4,
        },
        "backtest_worker": {
            "container": "tquant-backtest-worker-mysql",
            "container_present": True,
            "env": {
                "DB_POOL_SIZE": "2",
                "DB_MAX_OVERFLOW": "2",
                "RUNTIME_LOW_PRIORITY_TASKS_PAUSED": "true",
                "BACKTEST_PARQUET_DAILY_BARS_ENABLED": "false",
            },
            "pool_budget": 4,
        },
        "analytics_worker": {
            "container": "tquant-analytics-worker-mysql",
            "container_present": True,
            "env": {
                "DB_POOL_SIZE": "4",
                "DB_MAX_OVERFLOW": "4",
                "RUNTIME_LOW_PRIORITY_TASKS_PAUSED": "true",
                "TQUANT_ANALYTICS_ENABLED": "true",
                "TQUANT_DUCKDB_THREADS": "2",
            },
            "pool_budget": 8,
        },
    }
    report: dict[str, object] = {
        "generated_at": "2026-06-08T00:00:00+00:00",
        "mysql": {"max_connections": 120, "threads_connected": 8, "threads_running": 1},
        "pool_budget": {"total": 28, "target": 40},
        "roles": roles,
        "commands": {
            "compose_config": {"returncode": 0},
            "mysql_status": {"returncode": 0},
        },
    }
    report.update(overrides)
    return report


def test_platform_budget_report_passes_bounded_fixture(tmp_path: Path) -> None:
    result = run_budget_report(sample_budget_report(), tmp_path, "--fail-on-blocking")

    assert result.returncode == 0, result.stderr
    payload = json.loads((tmp_path / "budget.json").read_text(encoding="utf-8"))
    assert payload["evaluation"]["status"] == "ok"
    assert payload["evaluation"]["blocking"] == []
    assert payload["roles"]["runtime_scheduler"]["env"]["RUNTIME_BACKGROUND_COMPACT_MODE_ENABLED"] == "true"
    markdown = (tmp_path / "budget.md").read_text(encoding="utf-8")
    assert "| 应用连接池预算总和 | 28 |" in markdown
    assert "| web | tquant-app-mysql | 8 | n/a | false | false |" in markdown


def test_platform_budget_report_blocks_web_heavy_tasks(tmp_path: Path) -> None:
    fixture = sample_budget_report()
    roles = fixture["roles"]  # type: ignore[index]
    roles["web"]["env"]["RUNTIME_BACKGROUND_JOBS_ENABLED"] = "true"  # type: ignore[index]
    roles["web"]["env"]["TQUANT_ANALYTICS_ENABLED"] = "true"  # type: ignore[index]

    result = run_budget_report(fixture, tmp_path, "--fail-on-blocking")

    assert result.returncode == 42
    payload = json.loads((tmp_path / "budget.json").read_text(encoding="utf-8"))
    assert "web_background_jobs_enabled" in payload["evaluation"]["blocking"]
    assert "web_analytics_enabled" in payload["evaluation"]["blocking"]


def test_platform_budget_report_warns_on_large_pool_and_mysql_budget(tmp_path: Path) -> None:
    fixture = sample_budget_report(
        mysql={"max_connections": 300, "threads_connected": 8, "threads_running": 1},
        pool_budget={"total": 64, "target": 40},
    )

    result = run_budget_report(fixture, tmp_path)

    assert result.returncode == 0
    payload = json.loads((tmp_path / "budget.json").read_text(encoding="utf-8"))
    assert "mysql_max_connections=300" in payload["evaluation"]["warnings"]
    assert "pool_budget=64" in payload["evaluation"]["warnings"]


def test_platform_budget_report_warns_when_worker_pause_env_is_missing(tmp_path: Path) -> None:
    fixture = sample_budget_report()
    roles = fixture["roles"]  # type: ignore[index]
    del roles["analytics_worker"]["env"]["RUNTIME_LOW_PRIORITY_TASKS_PAUSED"]  # type: ignore[index]

    result = run_budget_report(fixture, tmp_path)

    assert result.returncode == 0
    payload = json.loads((tmp_path / "budget.json").read_text(encoding="utf-8"))
    assert "low_priority_pause_env_missing=analytics_worker" in payload["evaluation"]["warnings"]


def test_platform_budget_verifier_is_read_only() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "docker compose up" not in script
    assert "docker restart" not in script
    assert "docker system prune" not in script
    assert "docker volume prune" not in script
    assert "DELETE FROM" not in script
    assert "UPDATE " not in script
    assert "PURGE BINARY LOGS" not in script


def test_platform_budget_compose_parser_redacts_sensitive_environment() -> None:
    parser = runpy.run_path(str(SCRIPT))["parse_compose_config"]

    payload = parser(
        "services:\n"
        "  app:\n"
        "    environment:\n"
        "      ADMIN_API_TOKEN: should-not-leak\n"
        "      AUTH_SECRET_KEY: should-not-leak\n"
        "      MYSQL_PASSWORD: should-not-leak\n"
        "      DB_POOL_SIZE: \"4\"\n"
        "      DB_MAX_OVERFLOW: \"4\"\n"
        "      RUNTIME_BACKGROUND_JOBS_ENABLED: \"false\"\n"
    )

    assert payload["service_env"]["app"] == {
        "DB_POOL_SIZE": "4",
        "DB_MAX_OVERFLOW": "4",
        "RUNTIME_BACKGROUND_JOBS_ENABLED": "false",
    }
    dumped = json.dumps(payload)
    assert "should-not-leak" not in dumped
    assert "ADMIN_API_TOKEN" not in dumped
