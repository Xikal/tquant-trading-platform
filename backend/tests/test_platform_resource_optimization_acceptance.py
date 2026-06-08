from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "scripts" / "render_platform_resource_optimization_acceptance.py"


def run_acceptance(tmp_path: Path, reports: dict[str, dict[str, object]]) -> subprocess.CompletedProcess[str]:
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
            "--readiness-report",
            str(paths["readiness"]),
            "--maintenance-plan",
            str(paths["maintenance"]),
            "--chunk-profile",
            str(paths["chunk"]),
            "--completion-audit",
            str(paths["completion"]),
            "--cloud-performance-report",
            str(paths["cloud_performance"]),
            "--backup-verification-report",
            str(paths["backup_verification"]),
            "--json-output",
            str(tmp_path / "acceptance.json"),
            "--markdown-output",
            str(tmp_path / "acceptance.md"),
        ],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )


def test_acceptance_report_exposes_cutover_blockers_and_safety_boundaries(tmp_path: Path) -> None:
    result = run_acceptance(tmp_path, _current_like_reports())

    assert result.returncode == 0, result.stderr
    report = json.loads((tmp_path / "acceptance.json").read_text(encoding="utf-8"))
    assert report["status"] == "blocking"
    assert report["formal_cutover_status"] == "not_ready"
    assert report["deployed"] is False
    assert report["cutover"] is False
    assert report["old_frontend_modified"] is False
    assert report["strategy_policy_modified"] is False
    assert report["production_semantics_changed"] is False
    assert report["cutover_requires_separate_authorization"] is True
    assert report["resource_state"]["mysql_backup"]["count"] == 1
    assert report["resource_state"]["mysql_backup_verification"]["gzip_ok"] is True
    assert report["resource_state"]["mysql_backup_verification"]["sql_signature_ok"] is True
    assert report["resource_state"]["deploy_backups"]["count"] == 0
    assert report["parquet_manifest_state"]["blocked_count"] == 9
    assert report["completion_audit"]["status"] == "blocking"
    assert report["completion_audit"]["summary"]["blocked"] == 8
    assert report["online_performance_state"]["ok"] is True
    assert report["online_performance_state"]["report"].endswith("cloud_performance.json")
    assert report["online_performance_state"]["report"] in report["validation_references"]
    assert report["before_after"]["online_monitor_bff_p95_ms"] == 30.2
    assert "blocking:manifest:manifest_blocked_count=9" in report["open_items"]
    assert "production_score" in report["backend_change_reason"]

    markdown = (tmp_path / "acceptance.md").read_text(encoding="utf-8")
    assert "frontend-next 与平台资源优化验收草案" in markdown
    assert "旧 frontend 是否未改：`True`" in markdown
    assert "正式 cutover 状态：`not_ready`" in markdown
    assert "Cutover 前必须补齐" in markdown
    assert "monitor_bff p95：`30.2` ms" in markdown
    assert "cloud_performance.json" in markdown
    assert "MySQL 备份 gzip 完整：`True`" in markdown
    assert "/home/ubuntu/mysql-backups/tquant-all-databases.sql.gz" in markdown


def test_acceptance_source_is_report_only_and_non_destructive() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "subprocess.run" not in script
    assert "os.system" not in script
    assert "DELETE FROM" not in script
    assert "UPDATE " not in script
    assert "DROP TABLE" not in script
    assert "PURGE BINARY LOGS" not in script
    assert "docker volume prune" not in script
    assert "rm -rf" not in script
    assert "RuntimeTaskQueue" not in script


def _current_like_reports() -> dict[str, dict[str, object]]:
    return {
        "resource": {
            "root": {"used_pct": 56},
            "memory": {"swap": {"used_pct": 100.0}},
            "mysql": {
                "slow_log": {"size_bytes": 3_328_599_654},
                "variables": {"binlog_expire_logs_seconds": 259200, "max_binlog_size": 1_073_741_824},
                "binary_logs": {"count": 5, "total_bytes": 4_700_000_000},
            },
            "docker": {"build_cache": {"size_bytes": 6_400_575_012}, "local_volumes": {"size_bytes": 11_400_000_000}},
            "deploy_backups": {"count": 0, "total_bytes": 0, "rows": []},
            "mysql_backups": {
                "count": 1,
                "total_bytes": 147_000_000,
                "latest": {"path": "/home/ubuntu/mysql-backups/tquant-all-databases.sql.gz"},
                "rows": [],
            },
            "evaluation": {
                "status": "warning",
                "warnings": ["swap_used_pct=100.0", "mysql_slow_log_bytes=3328599654"],
                "blocking": [],
            },
        },
        "budget": {
            "mysql": {"max_connections": 300, "threads_connected": 21, "threads_running": 2},
            "pool_budget": {"total": 28},
            "evaluation": {"status": "warning", "warnings": ["mysql_max_connections=300"], "blocking": []},
        },
        "manifest": {
            "summary": {
                "ready_count": 1,
                "missing_count": 9,
                "blocked_count": 9,
                "verified_files": 25,
                "blocked_datasets": ["strategy_tracking_snapshots"],
            },
            "evaluation": {
                "status": "blocking",
                "warnings": ["manifest_missing_count=9"],
                "blocking": ["manifest_blocked_count=9"],
            },
        },
        "readiness": {
            "evaluation": {
                "status": "blocking",
                "blocking": ["manifest:manifest_blocked_count=9"],
                "warnings": ["resource:swap_used_pct=100.0"],
            }
        },
        "maintenance": {
            "steps": [{"id": "preflight_resource_readiness"}, {"id": "analytics_manifest_enqueue"}],
            "safety": {"operator_apply_steps": ["resource_limits_apply", "analytics_manifest_enqueue"]},
        },
        "chunk": {
            "summary": {
                "initial_js_raw_bytes": 282_841,
                "initial_echarts_asset_count": 0,
            }
        },
        "completion": {
            "status": "blocking",
            "summary": {"passed": 15, "warning": 3, "blocked": 8, "not_verified": 1, "total": 27},
        },
        "cloud_performance": {
            "ok": True,
            "failures": [],
            "api": [
                {"name": "readyz", "statuses": [200], "p95_ms": 7.3},
                {"name": "monitor_bff", "statuses": [200], "p95_ms": 30.2},
                {"name": "market_pulse", "statuses": [200], "p95_ms": 28.2},
                {"name": "priority_board", "statuses": [200], "p95_ms": 103.4},
                {"name": "watchlist_signals", "statuses": [200], "p95_ms": 24.1},
            ],
        },
        "backup_verification": {
            "backup": {
                "path": "/home/ubuntu/mysql-backups/tquant-all-databases.sql.gz",
                "size_bytes": 135_000_000,
                "gzip_ok": True,
                "sql_signature_ok": True,
                "sha256": "abc123",
            },
            "evaluation": {"status": "ok", "blocking": [], "warnings": []},
        },
    }
