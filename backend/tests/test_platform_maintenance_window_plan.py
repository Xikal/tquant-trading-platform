from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "scripts" / "plan_platform_maintenance_window.py"


def run_plan(tmp_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    readiness = tmp_path / "readiness.json"
    export_plan = tmp_path / "export-plan.json"
    readiness.write_text(
        json.dumps(
            {
                "evaluation": {
                    "status": "blocking",
                    "blocking": ["manifest:manifest_blocked_count=9"],
                    "warnings": ["resource:swap_used_pct=100.0"],
                }
            }
        ),
        encoding="utf-8",
    )
    export_plan.write_text(
        json.dumps(
            {
                "summary": {
                    "required_tasks": ["analytics_export_strategy_tracking_snapshots"],
                    "blocked_datasets": ["strategy_tracking_snapshots"],
                }
            }
        ),
        encoding="utf-8",
    )
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--readiness-report",
            str(readiness),
            "--export-plan",
            str(export_plan),
            "--date-tag",
            "2026-06-08",
            "--json-output",
            str(tmp_path / "plan.json"),
            "--markdown-output",
            str(tmp_path / "plan.md"),
            *extra,
        ],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )


def test_maintenance_plan_generates_ordered_manual_steps(tmp_path: Path) -> None:
    result = run_plan(tmp_path)

    assert result.returncode == 0
    plan = json.loads((tmp_path / "plan.json").read_text(encoding="utf-8"))
    step_ids = [item["id"] for item in plan["steps"]]
    assert step_ids == [
        "preflight_resource_readiness",
        "resource_limits_dry_run",
        "resource_limits_apply",
        "post_resource_verify",
        "analytics_manifest_preflight",
        "analytics_manifest_enqueue",
        "analytics_worker_observe",
        "analytics_manifest_post_verify",
        "final_validation_gates",
    ]
    assert plan["safety"]["does_execute_commands"] is False
    assert plan["safety"]["does_deploy"] is False
    assert plan["safety"]["does_cutover"] is False
    assert plan["safety"]["does_clean_mysql_source_tables"] is False
    assert plan["safety"]["operator_apply_steps"] == ["resource_limits_apply", "analytics_manifest_enqueue"]
    assert plan["execution"]["operator_working_directory"] == "/Users/j/Documents/gupiao"
    assert plan["execution"]["remote_host"] == "43.143.243.97"
    assert plan["execution"]["remote_project_dir"] == "/home/ubuntu/gupiao-upload"
    assert plan["execution"]["mysql_slow_log"].endswith("mysql-slow.log")
    assert "stop on the first non-zero exit" in plan["execution"]["failure_policy"]
    dry_run_step = next(item for item in plan["steps"] if item["id"] == "resource_limits_dry_run")
    assert any("platform-resource-limits-dry-run-2026-06-08.json" in command for command in dry_run_step["commands"])
    assert any(command.startswith("scp -i") for command in dry_run_step["commands"])
    apply_step = next(item for item in plan["steps"] if item["id"] == "resource_limits_apply")
    assert any("ssh -i" in command and "/home/ubuntu/gupiao-upload" in command for command in apply_step["commands"])
    assert any("sudo docker compose -f docker-compose.mysql.yml up -d mysql" in command for command in apply_step["commands"])
    assert any("platform-resource-limits-apply-2026-06-08.json" in command for command in apply_step["commands"])
    assert any(command.startswith("scp -i") for command in apply_step["commands"])
    assert any("/home/ubuntu/mysql-backups/slow-log/mysql-slow-$TS.log" in command for command in apply_step["commands"])
    assert any("sudo logrotate -f /etc/logrotate.d/tquant-mysql-slow-log" in command for command in apply_step["commands"])
    assert "sudo docker compose -f docker-compose.mysql.yml restart mysql" not in apply_step["commands"]
    preflight_step = next(item for item in plan["steps"] if item["id"] == "preflight_resource_readiness")
    assert any("test -f scripts/install_platform_resource_limits.py" in command for command in preflight_step["commands"])
    assert any("--ssh-host 43.143.243.97" in command for command in preflight_step["commands"])
    assert any("verify_mysql_backup_artifact.py" in command for command in preflight_step["commands"])
    assert any(
        "--backup-verification-report docs/reports/platform-mysql-backup-verification-2026-06-08.json" in command
        for command in preflight_step["commands"]
    )
    post_verify_step = next(item for item in plan["steps"] if item["id"] == "post_resource_verify")
    assert any("curl -f http://127.0.0.1:18090/readyz" in command and "ssh -i" in command for command in post_verify_step["commands"])
    assert any("--ssh-host 43.143.243.97" in command for command in post_verify_step["commands"])
    assert any("platform-mysql-backup-verification-after-limits-2026-06-08.json" in command for command in post_verify_step["commands"])
    manifest_preflight = next(item for item in plan["steps"] if item["id"] == "analytics_manifest_preflight")
    assert any("--ssh-host 43.143.243.97" in command for command in manifest_preflight["commands"])
    enqueue_step = next(item for item in plan["steps"] if item["id"] == "analytics_manifest_enqueue")
    assert any(command.startswith("scp -i") for command in enqueue_step["commands"])
    assert any("PYTHONPATH=backend:. python3 scripts/submit_analytics_manifest_exports.py" in command for command in enqueue_step["commands"])
    assert any("platform-analytics-export-submission-apply-2026-06-08.json" in command for command in enqueue_step["commands"])
    worker_observe = next(item for item in plan["steps"] if item["id"] == "analytics_worker_observe")
    assert all("ssh -i" in command and "ADMIN_API_TOKEN" in command for command in worker_observe["commands"])
    post_manifest_step = next(item for item in plan["steps"] if item["id"] == "analytics_manifest_post_verify")
    assert any("--ssh-host 43.143.243.97" in command for command in post_manifest_step["commands"])
    assert any(
        "--backup-verification-report docs/reports/platform-mysql-backup-verification-after-limits-2026-06-08.json" in command
        for command in post_manifest_step["commands"]
    )
    assert any("platform-analytics-export-plan-after-export-2026-06-08.json" in command for command in post_manifest_step["commands"])
    assert any(
        "platform-analytics-export-submission-dry-run-after-export-2026-06-08.json" in command
        for command in post_manifest_step["commands"]
    )
    final_readiness = post_manifest_step["commands"][-1]
    assert "--resource-report docs/reports/platform-resource-after-limits-2026-06-08.json" in final_readiness
    assert "--budget-report docs/reports/platform-budget-after-limits-2026-06-08.json" in final_readiness
    assert "--manifest-report docs/reports/platform-analytics-manifests-after-export-2026-06-08.json" in final_readiness
    assert "--export-plan docs/reports/platform-analytics-export-plan-after-export-2026-06-08.json" in final_readiness
    assert "--submission-report docs/reports/platform-analytics-export-submission-dry-run-after-export-2026-06-08.json" in final_readiness
    final_gate_step = next(item for item in plan["steps"] if item["id"] == "final_validation_gates")
    assert final_gate_step["requires_operator"] is False
    assert final_gate_step["destructive"] is False
    assert any("--verify-only --performance-verify --performance-rounds 3" in command for command in final_gate_step["commands"])
    frontend_command = next(command for command in final_gate_step["commands"] if "npm run api:check && npm run typecheck" in command)
    assert frontend_command.startswith("(cd frontend-next && ")
    assert frontend_command.endswith(")")
    assert not any(command.startswith("cd frontend-next && ") for command in final_gate_step["commands"])
    assert any(command.startswith("PYTHONPATH=backend:.") for command in final_gate_step["commands"])
    assert any("verify_go_rust_performance_acceptance.py" in command for command in final_gate_step["commands"])
    acceptance_command = next(
        command for command in final_gate_step["commands"] if "render_platform_resource_optimization_acceptance.py" in command
    )
    assert "--resource-report docs/reports/platform-resource-after-limits-2026-06-08.json" in acceptance_command
    assert "--budget-report docs/reports/platform-budget-after-limits-2026-06-08.json" in acceptance_command
    assert "--manifest-report docs/reports/platform-analytics-manifests-after-export-2026-06-08.json" in acceptance_command
    assert "--readiness-report docs/reports/platform-optimization-readiness-after-export-2026-06-08.json" in acceptance_command
    assert "--backup-verification-report docs/reports/platform-mysql-backup-verification-after-limits-2026-06-08.json" in acceptance_command
    assert '--cloud-performance-report "$(ls -t docs/reports/gupiao-cloud-performance-*.json | head -1)"' in acceptance_command
    assert "platform-resource-optimization-acceptance-after-export-2026-06-08" in acceptance_command
    audit_command = next(
        command for command in final_gate_step["commands"] if "audit_platform_resource_optimization_completion.py" in command
    )
    assert "--acceptance-report docs/reports/platform-resource-optimization-acceptance-after-export-2026-06-08.json" in audit_command
    assert "--resource-report docs/reports/platform-resource-after-limits-2026-06-08.json" in audit_command
    assert "--budget-report docs/reports/platform-budget-after-limits-2026-06-08.json" in audit_command
    assert "--manifest-report docs/reports/platform-analytics-manifests-after-export-2026-06-08.json" in audit_command
    assert "--readiness-report docs/reports/platform-optimization-readiness-after-export-2026-06-08.json" in audit_command
    assert "--backup-verification-report docs/reports/platform-mysql-backup-verification-after-limits-2026-06-08.json" in audit_command
    assert '--cloud-performance-report "$(ls -t docs/reports/gupiao-cloud-performance-*.json | head -1)"' in audit_command
    assert "platform-resource-optimization-completion-audit-after-export-2026-06-08" in audit_command
    assert any(command == 'test -n "$(ls -t docs/reports/gupiao-cloud-performance-*.json | head -1)"' for command in final_gate_step["commands"])
    assert "git diff --check" in final_gate_step["commands"]
    assert any("strategy_policy" in command and "^frontend/" in command for command in final_gate_step["commands"])
    assert any("--confirm-apply submit-analytics-manifest-exports" in command for command in enqueue_step["commands"])
    markdown = (tmp_path / "plan.md").read_text(encoding="utf-8")
    assert "平台资源优化运维窗口执行计划" in markdown
    assert "不执行命令、不部署、不切流" in markdown
    assert "远端项目目录：`/home/ubuntu/gupiao-upload`" in markdown
    assert "MySQL slow log：`/var/lib/docker/volumes/tquant-mysql_mysql_data/_data/mysql-slow.log`" in markdown
    assert "任一命令失败即停止" in markdown


def test_maintenance_plan_source_is_non_executing_and_non_destructive() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "subprocess.run" not in script
    assert "os.system" not in script
    assert "DELETE FROM" not in script
    assert "UPDATE " not in script
    assert "DROP TABLE" not in script
    assert "PURGE BINARY LOGS" not in script
    assert "docker volume prune" not in script
    assert "rm -rf" not in script
    assert "verify_mysql_backup_artifact.py" in script
    assert "--backup-verification-report" in script
    assert "--cloud-performance-report" in script
    assert "gupiao-cloud-performance-*.json" in script
    assert "--performance-rounds 3" in script
    assert "git diff --check" in script
    assert "--apply" in script
    assert "does_execute_commands" in script
    assert "ssh_command_prefix" in script
    assert "scp_command_prefix" in script
