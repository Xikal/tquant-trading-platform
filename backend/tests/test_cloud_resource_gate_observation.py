from __future__ import annotations

import json
import runpy
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "scripts" / "collect_cloud_resource_gate_observation.py"


def run_observation(fixture: dict[str, object], tmp_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    fixture_path = tmp_path / "fixture.json"
    report_path = tmp_path / "gate.json"
    markdown_path = tmp_path / "gate.md"
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


def sample_gate_report(**overrides: object) -> dict[str, object]:
    report: dict[str, object] = {
        "generated_at": "2026-06-12T00:00:00+00:00",
        "source": {"remote_user": "ubuntu", "remote_host": "43.143.243.97"},
        "host": {
            "date": "Fri Jun 12 00:00:00 CST 2026",
            "uptime": "00:00:00 up 2 days, load average: 0.24, 0.27, 0.33",
            "memory": {
                "mem": {"total_mb": 3723, "used_mb": 2077, "free_mb": 600, "available_mb": 1645, "used_pct": 55.79},
                "swap": {"total_mb": 2047, "used_mb": 700, "free_mb": 1347, "used_pct": 34.2},
            },
            "root": {"used_pct": 61},
            "root_inode": {"used_pct": 12},
        },
        "docker": {
            "compose_ps": {
                "rows": [
                    {"name": "tquant-app-mysql", "status": "Up 1 hour (healthy)"},
                    {"name": "tquant-mysql", "status": "Up 1 hour (healthy)"},
                    {"name": "tquant-redis", "status": "Up 2 days (healthy)"},
                    {"name": "tquant-runtime-worker-mysql", "status": "Up 30 minutes (healthy)"},
                    {"name": "tquant-runtime-scheduler-mysql", "status": "Up 1 hour (healthy)"},
                ],
                "missing_expected": [],
            },
            "stats": {
                "rows": [
                    {
                        "name": "tquant-app-mysql",
                        "cpu_percent": "0.01%",
                        "memory_usage": "44.82MiB / 768MiB",
                        "memory_percent": "5.84%",
                        "memory_pct": 5.84,
                    },
                    {
                        "name": "tquant-runtime-worker-mysql",
                        "cpu_percent": "0.12%",
                        "memory_usage": "162.2MiB / 768MiB",
                        "memory_percent": "21.12%",
                        "memory_pct": 21.12,
                    },
                    {
                        "name": "tquant-runtime-scheduler-mysql",
                        "cpu_percent": "0.10%",
                        "memory_usage": "358.7MiB / 640MiB",
                        "memory_percent": "56.05%",
                        "memory_pct": 56.05,
                    },
                    {
                        "name": "tquant-mysql",
                        "cpu_percent": "0.30%",
                        "memory_usage": "632.7MiB / 1.5GiB",
                        "memory_percent": "41.18%",
                        "memory_pct": 41.18,
                    },
                ]
            },
        },
        "http": [
            {"path": "/readyz", "status": 200, "time_total": 0.006, "returncode": 0, "error": ""},
            {"path": "/api/monitor", "status": 404, "time_total": 0.004, "returncode": 0, "error": ""},
            {"path": "/api/monitor/snapshot", "status": 401, "time_total": 0.005, "returncode": 0, "error": ""},
            {"path": "/api/priority-board", "status": 404, "time_total": 0.003, "returncode": 0, "error": ""},
            {"path": "/api/screeners/low-buy/priority-board", "status": 401, "time_total": 0.006, "returncode": 0, "error": ""},
            {"path": "/api/runtime-tasks/summary", "status": 401, "time_total": 0.004, "returncode": 0, "error": ""},
            {"path": "/next/monitor", "status": 200, "time_total": 0.009, "returncode": 0, "error": ""},
            {"path": "/next/monitor/market", "status": 200, "time_total": 0.008, "returncode": 0, "error": ""},
            {"path": "/next/strategy-tracking", "status": 200, "time_total": 0.008, "returncode": 0, "error": ""},
            {"path": "/next/analysis", "status": 200, "time_total": 0.008, "returncode": 0, "error": ""},
            {"path": "/next/backtest", "status": 200, "time_total": 0.008, "returncode": 0, "error": ""},
            {"path": "/next/data", "status": 200, "time_total": 0.008, "returncode": 0, "error": ""},
            {"path": "/next/settings", "status": 200, "time_total": 0.008, "returncode": 0, "error": ""},
        ],
        "mysql": {
            "status": {"Threads_connected": "8", "Threads_running": "2", "Slow_queries": "0"},
            "variables": {"max_connections": "120", "innodb_buffer_pool_size": "536870912"},
            "table_space": [{"table_schema": "tquant", "mb": "512.00"}],
        },
        "runtime_tasks": {
            "recent_summary": [
                {
                    "task_type": "low_buy_materialization_refresh",
                    "status": "succeeded",
                    "count": "2",
                    "oldest": "2026-06-12 00:00:00",
                    "latest": "2026-06-12 00:10:00",
                },
                {
                    "task_type": "strategy_tracking_snapshot_refresh",
                    "status": "succeeded",
                    "count": "2",
                    "oldest": "2026-06-12 00:00:00",
                    "latest": "2026-06-12 00:10:00",
                },
            ],
            "nonterminal": [],
            "heartbeats": [
                {"key": "platform_component.heartbeat.runtime-scheduler", "updated_at": "2026-06-12 00:10:00", "value_prefix": "{}"},
                {"key": "platform_component.heartbeat.runtime-worker", "updated_at": "2026-06-12 00:10:00", "value_prefix": "{}"},
            ],
        },
        "logs": {"oom": "", "worker_signals": "", "scheduler_provider_signals": ""},
    }
    report.update(overrides)
    return report


def test_clean_observation_still_blocks_d5_without_full_trading_day(tmp_path: Path) -> None:
    result = run_observation(sample_gate_report(), tmp_path, "--fail-on-d5-blocked")

    assert result.returncode == 42
    payload = json.loads((tmp_path / "gate.json").read_text(encoding="utf-8"))
    assert payload["evaluation"]["status"] == "ok"
    assert payload["evaluation"]["d5_gate"]["ready"] is False
    assert "full_trading_day_observation_incomplete" in payload["evaluation"]["d5_gate"]["blockers"]
    markdown = (tmp_path / "gate.md").read_text(encoding="utf-8")
    assert "No Docker restart/recreate/remove" in markdown


def test_clean_observation_can_pass_d5_gate_after_full_trading_day(tmp_path: Path) -> None:
    result = run_observation(sample_gate_report(), tmp_path, "--full-trading-day-complete", "--fail-on-d5-blocked")

    assert result.returncode == 0, result.stderr
    payload = json.loads((tmp_path / "gate.json").read_text(encoding="utf-8"))
    assert payload["evaluation"]["status"] == "ok"
    assert payload["evaluation"]["d5_gate"]["ready"] is True
    assert payload["evaluation"]["d5_gate"]["blockers"] == []


def test_observation_blocks_on_core_http_failure(tmp_path: Path) -> None:
    fixture = sample_gate_report(
        http=[
            {"path": "/readyz", "status": 200, "time_total": 0.006, "returncode": 0, "error": ""},
            {"path": "/next/monitor", "status": 500, "time_total": 0.5, "returncode": 0, "error": ""},
        ]
    )

    result = run_observation(fixture, tmp_path, "--full-trading-day-complete", "--fail-on-d5-blocked")

    assert result.returncode == 42
    payload = json.loads((tmp_path / "gate.json").read_text(encoding="utf-8"))
    assert "http_status:/next/monitor=500" in payload["evaluation"]["blocking"]
    assert "http_status:/next/monitor=500" in payload["evaluation"]["d5_gate"]["blockers"]


def test_observation_keeps_d5_blocked_on_worker_or_scheduler_pressure(tmp_path: Path) -> None:
    fixture = sample_gate_report()
    fixture["docker"]["stats"]["rows"][1]["memory_percent"] = "92.00%"  # type: ignore[index]
    fixture["docker"]["stats"]["rows"][1]["memory_pct"] = 92.0  # type: ignore[index]
    fixture["logs"] = {
        "oom": "",
        "worker_signals": "",
        "scheduler_provider_signals": "\n".join(
            f"market provider circuit open: eastmoney {index}" for index in range(20)
        ),
    }
    fixture["runtime_tasks"] = {
        **fixture["runtime_tasks"],  # type: ignore[arg-type]
        "nonterminal": [
            {
                "status": "queued",
                "task_type": "data_quality_sla_refresh",
                "priority": "22",
                "count": "2",
                "oldest": "2026-06-12 00:00:00",
                "latest": "2026-06-12 00:01:00",
            }
        ],
    }

    result = run_observation(fixture, tmp_path, "--full-trading-day-complete", "--fail-on-d5-blocked")

    assert result.returncode == 42
    payload = json.loads((tmp_path / "gate.json").read_text(encoding="utf-8"))
    warnings = payload["evaluation"]["warnings"]
    blockers = payload["evaluation"]["d5_gate"]["blockers"]
    assert "runtime_worker_memory_pct=92.0" in warnings
    assert "scheduler_provider_warning_lines=20" in warnings
    assert "runtime_nonterminal_task_count=2" in warnings
    assert "scheduler_provider_warning_lines=20" in blockers


def test_observation_treats_low_frequency_provider_recovery_probe_as_warning_only(
    tmp_path: Path,
) -> None:
    fixture = sample_gate_report()
    fixture["logs"] = {
        "oom": "",
        "worker_signals": "",
        "scheduler_provider_signals": "\n".join(
            f"market provider result not usable: board_breadth {index}" for index in range(5)
        ),
    }

    result = run_observation(fixture, tmp_path, "--full-trading-day-complete", "--fail-on-d5-blocked")

    assert result.returncode == 0, result.stderr
    payload = json.loads((tmp_path / "gate.json").read_text(encoding="utf-8"))
    warnings = payload["evaluation"]["warnings"]
    blockers = payload["evaluation"]["d5_gate"]["blockers"]
    assert "scheduler_provider_warning_lines_observed=5" in warnings
    assert "scheduler_provider_warning_lines_observed=5" not in blockers


def test_observation_parsers_cover_remote_sections() -> None:
    module = runpy.run_path(str(SCRIPT))
    parse_http = module["parse_http"]
    parse_stats = module["parse_docker_stats"]
    parse_ps = module["parse_compose_ps"]
    parse_rows = module["parse_mysql_rows"]

    http = parse_http("/readyz\t0\t200 0.005\n/next/monitor\t0\t200 0.010\n")
    stats = parse_stats("tquant-runtime-worker-mysql\t0.1%\t713.3MiB / 768MiB\t92.88%\n")
    ps = parse_ps("tquant-runtime-worker-mysql\tUp 10 minutes (healthy)\n")
    rows = parse_rows(
        "strategy_tracking_snapshot_refresh\tsucceeded\t2\t2026-06-12 00:00:00\t2026-06-12 00:01:00\n",
        ("task_type", "status", "count", "oldest", "latest"),
    )

    assert http[0]["status"] == 200
    assert stats["rows"][0]["memory_pct"] == 92.88
    assert "tquant-mysql" in ps["missing_expected"]
    assert rows[0]["task_type"] == "strategy_tracking_snapshot_refresh"


def test_observation_script_is_read_only_and_collects_required_paths() -> None:
    module_dir = ROOT_DIR / "scripts" / "cloud_resource_gate_observation"
    script = SCRIPT.read_text(encoding="utf-8") + "\n" + "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(module_dir.glob("*.py"))
    )

    forbidden = (
        "docker compose up",
        "docker restart",
        "docker rm",
        "docker system prune",
        "docker volume prune",
        "DELETE FROM",
        "UPDATE ",
        "INSERT INTO",
        "ALTER TABLE",
        "TRUNCATE",
        "PURGE BINARY LOGS",
        "nginx -s reload",
        "systemctl restart",
    )
    for text in forbidden:
        assert text not in script
    assert "Read-only D5 cloud resource gate observation collector" in script
    assert "/readyz" in script
    assert "/next/monitor/market" in script
    assert "/api/screeners/low-buy/priority-board" in script
    assert "sudo docker stats --no-stream" in script
    assert "SHOW GLOBAL STATUS LIKE 'Threads_%'" in script
