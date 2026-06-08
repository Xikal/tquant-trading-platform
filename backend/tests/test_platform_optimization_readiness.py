from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "scripts" / "verify_platform_optimization_readiness.py"


def _load_readiness():
    spec = importlib.util.spec_from_file_location("verify_platform_optimization_readiness", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_readiness(tmp_path: Path, reports: dict[str, dict[str, object]], *extra: str) -> subprocess.CompletedProcess[str]:
    paths = {}
    for name, payload in reports.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths[name] = path
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--resource-report",
            str(paths["resource"]),
            "--budget-report",
            str(paths["budget"]),
            "--manifest-report",
            str(paths["manifest"]),
            "--export-plan",
            str(paths["export_plan"]),
            "--submission-report",
            str(paths["submission"]),
            "--backup-verification-report",
            str(paths["backup_verification"]),
            "--json-output",
            str(tmp_path / "readiness.json"),
            "--markdown-output",
            str(tmp_path / "readiness.md"),
            *extra,
        ],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )


def test_readiness_reports_current_blocking_and_warnings(tmp_path: Path) -> None:
    result = run_readiness(tmp_path, _current_like_reports(), "--fail-on-blocking")

    assert result.returncode == 42
    payload = json.loads((tmp_path / "readiness.json").read_text(encoding="utf-8"))
    assert payload["evaluation"]["status"] == "blocking"
    assert "manifest:manifest_blocked_count=9" in payload["evaluation"]["blocking"]
    assert "resource:resource_config_missing=docker_daemon" in payload["evaluation"]["warnings"]
    assert "worker_budget:mysql_max_connections=300" in payload["evaluation"]["warnings"]
    assert "export_plan:required_task_count=9" in payload["evaluation"]["warnings"]
    assert payload["summary"]["blocking_count"] == 1
    assert payload["summary"]["ready_count"] == 2
    assert any(check["name"] == "mysql_backup_verification" and check["status"] == "ready" for check in payload["checks"])
    markdown = (tmp_path / "readiness.md").read_text(encoding="utf-8")
    assert "平台资源优化 Readiness 聚合报告" in markdown


def test_readiness_reports_ready_when_all_inputs_are_clear(tmp_path: Path) -> None:
    reports = _ready_reports()

    result = run_readiness(tmp_path, reports, "--fail-on-blocking")

    assert result.returncode == 0
    payload = json.loads((tmp_path / "readiness.json").read_text(encoding="utf-8"))
    assert payload["evaluation"]["status"] == "ready"
    assert payload["evaluation"]["blocking"] == []
    assert payload["evaluation"]["warnings"] == []
    assert payload["summary"]["ready_count"] == 6


def test_missing_backup_verification_blocks_maintenance_window(tmp_path: Path) -> None:
    reports = _ready_reports()
    reports["backup_verification"] = {
        "backup": {"present": True, "size_bytes": 2048, "gzip_ok": False, "sql_signature_ok": True},
        "evaluation": {"status": "blocking", "warnings": [], "blocking": ["gzip_test_failed"]},
    }

    result = run_readiness(tmp_path, reports, "--fail-on-blocking")

    assert result.returncode == 42
    payload = json.loads((tmp_path / "readiness.json").read_text(encoding="utf-8"))
    assert payload["evaluation"]["status"] == "blocking"
    assert "mysql_backup:gzip_test_failed" in payload["evaluation"]["blocking"]
    assert "mysql_backup:gzip_ok=False" in payload["evaluation"]["blocking"]
    assert "Create and verify a fresh MySQL .sql.gz backup" in "\n".join(payload["next_actions"])


def test_submission_mismatch_blocks_apply_window() -> None:
    module = _load_readiness()
    check = module.submission_readiness(
        {"summary": {"selected_task_count": 1, "submitted_task_count": 0}, "safety": {"requires_apply_flag": True}},
        {"summary": {"required_task_count": 2}},
    )

    assert check["status"] == "blocking"
    assert "submission:selected_task_count=1:required_task_count=2" in check["blocking"]
    assert "submission:apply_confirmation_guard_missing" in check["blocking"]


def test_readiness_source_is_aggregate_only_and_non_destructive() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "DELETE FROM" not in script
    assert "UPDATE " not in script
    assert "DROP TABLE" not in script
    assert "PURGE BINARY LOGS" not in script
    assert "docker volume prune" not in script
    assert "RuntimeTaskQueue" not in script
    assert "subprocess.run" not in script
    assert "gzip -t" not in script


def _current_like_reports() -> dict[str, dict[str, object]]:
    return {
        "resource": {
            "root": {"used_pct": 56},
            "memory": {"swap": {"used_pct": 100.0}},
            "mysql": {"slow_log": {"size_bytes": 3328599654}, "variables": {"max_binlog_size": 1073741824}},
            "docker": {"build_cache": {"size_bytes": 6400575012}},
            "evaluation": {
                "status": "warning",
                "warnings": [
                    "swap_used_pct=100.0",
                    "mysql_slow_log_bytes=3328599654",
                    "docker_build_cache_bytes=6400575012",
                    "max_binlog_size=1073741824",
                    "resource_config_missing=docker_daemon",
                ],
                "blocking": [],
            },
        },
        "budget": {
            "mysql": {"max_connections": 300, "threads_connected": 21},
            "pool_budget": {"total": 28},
            "evaluation": {
                "status": "warning",
                "warnings": ["mysql_max_connections=300", "low_priority_pause_env_missing=runtime_worker"],
                "blocking": [],
            },
        },
        "manifest": {
            "summary": {"ready_count": 1, "missing_count": 9, "blocked_count": 9, "verified_files": 25},
            "evaluation": {
                "status": "blocking",
                "warnings": ["manifest_missing_count=9"],
                "blocking": ["manifest_blocked_count=9"],
            },
        },
        "export_plan": {
            "summary": {"required_task_count": 9, "required_tasks": ["analytics_export_strategy_tracking_snapshots"]},
            "safety": {
                "does_enqueue_tasks": False,
                "does_run_exporters": False,
                "does_modify_mysql": False,
                "does_clean_source_tables": False,
            },
            "evaluation": {"status": "blocking", "warnings": [], "blocking": ["manifest_export_required_count=9"]},
        },
        "submission": {
            "mode": "dry-run",
            "summary": {"selected_task_count": 9, "submitted_task_count": 0},
            "safety": {
                "requires_apply_flag": True,
                "requires_confirm_apply": True,
                "writes_runtime_tasks_only_when_apply": False,
            },
            "evaluation": {"status": "ready_to_submit", "warnings": [], "blocking": []},
        },
        "backup_verification": {
            "backup": {
                "present": True,
                "path": "/home/ubuntu/mysql-backups/tquant-all-databases-20260608-001016.sql.gz",
                "size_bytes": 140674550,
                "gzip_ok": True,
                "sql_signature_ok": True,
                "sha256": "f82db5fa2334fdd84abc4f7d2e136fd3af82742354ebb6a3bb24767215380db5",
                "sql_signatures": ["-- MySQL dump", "CREATE TABLE", "INSERT INTO", "LOCK TABLES"],
            },
            "evaluation": {"status": "ok", "warnings": [], "blocking": []},
        },
    }


def _ready_reports() -> dict[str, dict[str, object]]:
    return {
        "resource": {
            "root": {"used_pct": 45},
            "memory": {"swap": {"used_pct": 0}},
            "mysql": {"slow_log": {"size_bytes": 1}, "variables": {"max_binlog_size": 268435456}},
            "docker": {"build_cache": {"size_bytes": 1}},
            "evaluation": {"status": "ok", "warnings": [], "blocking": []},
        },
        "budget": {
            "mysql": {"max_connections": 120, "threads_connected": 8},
            "pool_budget": {"total": 24},
            "evaluation": {"status": "ok", "warnings": [], "blocking": []},
        },
        "manifest": {
            "summary": {"ready_count": 10, "missing_count": 0, "blocked_count": 0, "verified_files": 30},
            "evaluation": {"status": "ok", "warnings": [], "blocking": []},
        },
        "export_plan": {
            "summary": {"required_task_count": 0, "required_tasks": []},
            "safety": {
                "does_enqueue_tasks": False,
                "does_run_exporters": False,
                "does_modify_mysql": False,
                "does_clean_source_tables": False,
            },
            "evaluation": {"status": "ok", "warnings": [], "blocking": []},
        },
        "submission": {
            "mode": "dry-run",
            "summary": {"selected_task_count": 0, "submitted_task_count": 0},
            "safety": {
                "requires_apply_flag": True,
                "requires_confirm_apply": True,
                "writes_runtime_tasks_only_when_apply": False,
            },
            "evaluation": {"status": "empty", "warnings": [], "blocking": []},
        },
        "backup_verification": {
            "backup": {
                "present": True,
                "path": "/home/ubuntu/mysql-backups/tquant-all-databases-20260608-001016.sql.gz",
                "size_bytes": 140674550,
                "gzip_ok": True,
                "sql_signature_ok": True,
                "sha256": "f82db5fa2334fdd84abc4f7d2e136fd3af82742354ebb6a3bb24767215380db5",
                "sql_signatures": ["-- MySQL dump", "CREATE TABLE", "INSERT INTO", "LOCK TABLES"],
            },
            "evaluation": {"status": "ok", "warnings": [], "blocking": []},
        },
    }
