from __future__ import annotations

import json
import runpy
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "scripts" / "audit_platform_resource_optimization_completion.py"


def run_audit(
    tmp_path: Path,
    reports: dict[str, dict[str, object]],
    progress_text: str = "",
    *,
    fail_on_incomplete: bool = True,
) -> subprocess.CompletedProcess[str]:
    paths = {}
    for name, payload in reports.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths[name] = path
    progress = tmp_path / "progress.md"
    progress.write_text(progress_text, encoding="utf-8")
    cutover_runbook = tmp_path / "cutover.md"
    cutover_runbook.write_text(_runbook_text(), encoding="utf-8")
    production_runbook = tmp_path / "production.md"
    production_runbook.write_text(_runbook_text(), encoding="utf-8")
    mysql_runbook = tmp_path / "mysql.md"
    mysql_runbook.write_text(_mysql_runbook_text(), encoding="utf-8")
    command = [
        sys.executable,
        str(SCRIPT),
        "--acceptance-report",
        str(paths["acceptance"]),
        "--resource-report",
        str(paths["resource"]),
        "--budget-report",
        str(paths["budget"]),
        "--manifest-report",
        str(paths["manifest"]),
        "--readiness-report",
        str(paths["readiness"]),
        "--css-budget",
        str(paths["css_budget"]),
        "--chunk-profile",
        str(paths["chunk"]),
        "--backup-verification-report",
        str(paths["backup_verification"]),
        "--progress-report",
        str(progress),
        "--cloud-performance-report",
        str(paths["cloud_performance"]),
        "--cutover-runbook",
        str(cutover_runbook),
        "--production-runbook",
        str(production_runbook),
        "--mysql-runbook",
        str(mysql_runbook),
        "--json-output",
        str(tmp_path / "audit.json"),
        "--markdown-output",
        str(tmp_path / "audit.md"),
    ]
    if "frontend_perf" in paths:
        command.extend(["--frontend-perf-report", str(paths["frontend_perf"])])
    if fail_on_incomplete:
        command.append("--fail-on-incomplete")
    return subprocess.run(
        command,
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )


def test_completion_audit_reports_current_blocking_state(tmp_path: Path) -> None:
    result = run_audit(tmp_path, _current_like_reports(), _progress_text())

    assert result.returncode == 42
    payload = json.loads((tmp_path / "audit.json").read_text(encoding="utf-8"))
    assert payload["status"] == "blocking"
    by_id = {item["id"]: item for item in payload["checks"]}
    assert by_id["boundary.no_deploy_no_cutover"]["status"] == "passed"
    assert by_id["phase_a.available_memory"]["status"] == "warning"
    assert by_id["phase_a.max_binlog_size"]["status"] == "blocked"
    assert by_id["phase_a.slow_log_rotation"]["status"] == "blocked"
    assert by_id["phase_a.journal_retention"]["status"] == "blocked"
    assert by_id["phase_a.mysql_volume_short_term"]["status"] == "passed"
    assert by_id["phase_a.deploy_backup_retention"]["status"] == "passed"
    assert by_id["phase_a.mysql_backup"]["status"] == "passed"
    assert by_id["phase_b.css_important"]["status"] == "passed"
    assert by_id["phase_b.css_raw"]["status"] == "warning"
    assert by_id["phase_b.echarts_initial"]["status"] == "passed"
    assert by_id["phase_f.online_performance"]["status"] == "passed"
    assert by_id["phase_c.mysql_connections"]["status"] == "blocked"
    assert by_id["phase_d.all_required_manifests"]["status"] == "blocked"
    assert payload["summary"]["blocked"] >= 1

    markdown = (tmp_path / "audit.md").read_text(encoding="utf-8")
    assert "frontend-next 与平台资源优化完成度审计" in markdown
    assert "目标尚未完成" in markdown


def test_completion_audit_extracts_backend_passed_count_from_progress_text() -> None:
    module = runpy.run_path(str(SCRIPT))

    assert module["backend_passed_count"]("frontend-next 全链路通过，后端组合 133 passed。") == 133
    assert module["backend_passed_count"]("progress report records frontend-next full chain and backend 121 passed") == 121
    assert module["backend_passed_count"]("frontend-next 全链路通过，但后端未记录。") == 0


def test_completion_audit_can_report_ready_when_all_evidence_is_present(tmp_path: Path) -> None:
    reports = _ready_reports()
    result = run_audit(tmp_path, reports, _progress_text())

    assert result.returncode == 0, result.stderr
    payload = json.loads((tmp_path / "audit.json").read_text(encoding="utf-8"))
    assert payload["status"] == "ready"
    assert payload["summary"]["blocked"] == 0
    assert payload["summary"]["warning"] == 0
    assert payload["summary"]["not_verified"] == 0
    by_id = {item["id"]: item for item in payload["checks"]}
    assert by_id["phase_a.available_memory"]["status"] == "passed"
    assert by_id["phase_a.journal_retention"]["status"] == "passed"
    assert by_id["phase_b.strategy_bff_requests"]["status"] == "passed"
    assert by_id["phase_b.paper_virtualization_dom"]["status"] == "passed"
    assert by_id["phase_d.all_required_manifests"]["status"] == "passed"
    assert by_id["phase_e.deployment_resource_gate"]["status"] == "passed"
    assert "目标已具备完成证据" in payload["completion_statement"]


def test_completion_audit_source_is_read_only_and_non_destructive() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "subprocess.run" not in script
    assert "os.system" not in script
    assert "DELETE FROM" not in script
    assert "UPDATE " not in script
    assert "DROP TABLE" not in script
    assert "PURGE BINARY LOGS" not in script
    assert "docker volume prune" not in script
    assert "rm -rf" not in script
    assert "--apply" not in script


def _current_like_reports() -> dict[str, dict[str, object]]:
    return {
        "acceptance": {
            "deployed": False,
            "cutover": False,
            "old_frontend_modified": False,
            "strategy_policy_modified": False,
            "production_semantics_changed": False,
            "phase_completion": {"phase_e_prebuilt_deploy": "scripted_not_applied_online"},
            "status": "blocking",
            "open_items": ["blocking:manifest:manifest_blocked_count=9"],
        },
        "resource": {
            "root": {"used_pct": 56},
            "memory": {"mem": {"available_mb": 203}, "swap": {"used_pct": 100.0}},
            "journal": {"usage_bytes": 1_288_490_188},
            "mysql": {
                "variables": {"binlog_expire_logs_seconds": 259200, "max_binlog_size": 1_073_741_824},
                "slow_log": {"size_bytes": 3_328_599_654},
                "binary_logs": {"count": 5, "total_bytes": 4_734_095_738},
                "volume": {"rows": [{"size_bytes": 11_811_160_064}]},
            },
            "docker": {"build_cache": {"size_bytes": 6_400_575_012}},
            "deploy_backups": {"count": 0, "total_bytes": 0},
            "mysql_backups": {
                "count": 1,
                "latest": {"path": "/home/ubuntu/mysql-backups/tquant-all-databases.sql.gz"},
            },
        },
        "budget": {
            "mysql": {"max_connections": 300, "threads_connected": 21},
            "pool_budget": {"total": 28},
            "roles": {
                "web": {
                    "env": {
                        "RUNTIME_BACKGROUND_JOBS_ENABLED": "false",
                        "TQUANT_ANALYTICS_ENABLED": "false",
                    }
                }
            },
        },
        "manifest": {
            "summary": {
                "ready_count": 1,
                "ready_datasets": ["daily_bars"],
                "missing_count": 9,
                "blocked_count": 9,
                "verified_files": 25,
                "blocked_datasets": ["strategy_tracking_snapshots"],
            }
        },
        "readiness": {
            "evaluation": {
                "status": "blocking",
                "blocking": ["manifest:manifest_blocked_count=9"],
                "warnings": [
                    "resource:resource_config_missing=mysql_slow_logrotate",
                    "resource:resource_config_missing=buildkit",
                    "worker_budget:low_priority_pause_env_missing=runtime_worker",
                ],
            }
        },
        "css_budget": {
            "summary": {"important_count": 23, "source_css_bytes": 298_399},
            "budgets": {"source_css_important_target": 25, "source_css_bytes_target": 180_000},
            "status": {"source_css_bytes": "needs-explanation", "important_count": "ok"},
        },
        "chunk": {
            "summary": {"initial_echarts_assets": 0, "initial_js_raw_bytes": 282_841},
            "targets": {"initial_echarts_assets_max": 0, "initial_js_raw_bytes_max": 350_000},
        },
        "frontend_perf": {
            "strategy_tracking": {
                "api_request_count": 2,
                "items_422_count": 0,
                "forbidden_legacy_requests": [],
            },
            "paper": {"dom_nodes": 343, "non_mecha_descendants": 82, "mecha_descendants": 171},
        },
        "cloud_performance": _cloud_performance_report(),
        "backup_verification": _backup_verification_report(),
    }


def _ready_reports() -> dict[str, dict[str, object]]:
    reports = _current_like_reports()
    reports["acceptance"] = {
        **reports["acceptance"],
        "status": "ready",
        "open_items": [],
        "phase_completion": {"phase_e_prebuilt_deploy": "ready"},
    }
    reports["resource"] = {
        **reports["resource"],
        "root": {"used_pct": 55},
        "memory": {"mem": {"available_mb": 1024}, "swap": {"used_pct": 0.0}},
        "journal": {"usage_bytes": 100_000_000},
        "mysql": {
            "variables": {"binlog_expire_logs_seconds": 259200, "max_binlog_size": 268_435_456},
            "slow_log": {"size_bytes": 10_000_000},
            "binary_logs": {"count": 3, "total_bytes": 900_000_000},
            "volume": {"rows": [{"size_bytes": 8_000_000_000}]},
        },
        "docker": {"build_cache": {"size_bytes": 1_000_000_000}},
        "deploy_backups": {"count": 3, "total_bytes": 300_000_000},
    }
    reports["budget"] = {
        **reports["budget"],
        "mysql": {"max_connections": 120, "threads_connected": 15},
        "roles": {
            "web": {
                "env": {
                    "RUNTIME_BACKGROUND_JOBS_ENABLED": "false",
                    "TQUANT_ANALYTICS_ENABLED": "false",
                }
            }
        },
    }
    ready_datasets = [
        "daily_bars",
        "strategy_tracking_snapshots",
        "key_level_snapshots",
        "low_buy_result_snapshots",
        "backtest_runs",
        "backtest_trades",
        "backtest_daily_snapshots",
        "analysis_logs",
        "market_review_reports",
        "paper_review_reports",
    ]
    reports["manifest"] = {
        "summary": {
            "ready_count": len(ready_datasets),
            "ready_datasets": ready_datasets,
            "missing_count": 0,
            "blocked_count": 0,
            "verified_files": 40,
            "blocked_datasets": [],
        }
    }
    reports["readiness"] = {"evaluation": {"status": "ready", "blocking": [], "warnings": []}}
    reports["css_budget"] = {
        "summary": {"important_count": 20, "source_css_bytes": 170_000},
        "budgets": {"source_css_important_target": 25, "source_css_bytes_target": 180_000},
        "status": {"source_css_bytes": "ok", "important_count": "ok"},
    }
    reports["frontend_perf"] = {
        "strategy_tracking": {
            "api_request_count": 2,
            "items_422_count": 0,
            "forbidden_legacy_requests": [],
        },
        "paper": {"dom_nodes": 140, "non_mecha_descendants": 82, "mecha_descendants": 40},
    }
    reports["cloud_performance"] = _cloud_performance_report()
    reports["backup_verification"] = _backup_verification_report()
    return reports


def _cloud_performance_report() -> dict[str, object]:
    return {
        "ok": True,
        "failures": [],
        "api": [
            {"name": "readyz", "statuses": [200], "p95_ms": 7.3},
            {"name": "monitor_bff", "statuses": [200], "p95_ms": 30.2},
            {"name": "market_pulse", "statuses": [200], "p95_ms": 28.2},
            {"name": "priority_board", "statuses": [200], "p95_ms": 103.4},
            {"name": "watchlist_signals", "statuses": [200], "p95_ms": 24.1},
        ],
    }


def _backup_verification_report() -> dict[str, object]:
    return {
        "backup": {
            "present": True,
            "path": "/home/ubuntu/mysql-backups/tquant-all-databases.sql.gz",
            "size_bytes": 135_000_000,
            "gzip_ok": True,
            "sql_signature_ok": True,
            "sha256": "abc123",
        },
        "evaluation": {"status": "ok", "blocking": [], "warnings": []},
    }


def _progress_text() -> str:
    return (
        "首屏请求为 2 个，items` 422 为 0。"
        "非机甲页面 descendants `82`。"
        "RUNTIME_BACKGROUND_JOBS_ENABLED=false。"
        "frontend-next 全链路通过，后端组合 133 passed。"
    )


def _runbook_text() -> str:
    return (
        "资源 gate platform-optimization-readiness collect_platform_resource_report.py "
        "verify_platform_optimization_readiness.py --fail-on-blocking"
    )


def _mysql_runbook_text() -> str:
    return (
        "回滚 binlog slow log Analytics Manifest 热库保留窗口 manifest 恢复路径 "
        "不能自动清理 MySQL 源表"
    )
