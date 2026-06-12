from __future__ import annotations

import json
import runpy
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "scripts" / "audit_cloud_resource_remaining_closure.py"


def run_audit(tmp_path: Path, *, d5_ready: bool = False, missing: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    d5 = {
        "d5_ready": d5_ready,
        "full_trading_day_complete": d5_ready,
        "missing_checkpoints": [] if d5_ready else (missing or ["10:30", "11:30"]),
        "d5_blockers": [] if d5_ready else ["full_trading_day_observation_incomplete", "scheduler_provider_warning_lines=160"],
        "warnings": [] if d5_ready else ["mysql_slow_queries=145", "scheduler_provider_warning_lines=160"],
    }
    budget = {"evaluation": {"status": "ok"}}
    files = {
        "d5.json": json.dumps(d5),
        "budget.json": json.dumps(budget),
        "remediation.md": "DATA_QUALITY_SLA Disable Rollout\nno new `data_quality_sla_refresh` queued task appeared\nHistorical failed noise",
        "provider.md": "Configurable Cooldown Follow-Up",
        "domain.md": "Current Known Symptom\nTLS reset",
        "deployment.md": "--scope frontend-next\nfrontend-hot\nfrontend-legacy\nstop analytics-worker\nRUNTIME_LOW_PRIORITY_TASKS_PAUSED\nbacktest\nML\nfactor",
        "worker.md": "analytics-worker\nbacktest\nML\nfactor\nstop analytics-worker\nRUNTIME_LOW_PRIORITY_TASKS_PAUSED",
        "legacy.md": "frontend-hot\nfrontend-legacy",
        "main.py": "Legacy frontend assets have been retired",
    }
    paths: dict[str, Path] = {}
    for name, text in files.items():
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        paths[name] = path
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--d5-summary",
            str(paths["d5.json"]),
            "--budget-report",
            str(paths["budget.json"]),
            "--remediation-report",
            str(paths["remediation.md"]),
            "--provider-report",
            str(paths["provider.md"]),
            "--domain-runbook",
            str(paths["domain.md"]),
            "--deployment-runbook",
            str(paths["deployment.md"]),
            "--worker-runbook",
            str(paths["worker.md"]),
            "--legacy-runbook",
            str(paths["legacy.md"]),
            "--backend-main",
            str(paths["main.py"]),
            "--json-output",
            str(tmp_path / "audit.json"),
            "--markdown-output",
            str(tmp_path / "audit.md"),
            "--fail-on-blocked",
        ],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )


def test_remaining_audit_blocks_scheduler_embed_until_d5_is_ready(tmp_path: Path) -> None:
    result = run_audit(tmp_path, d5_ready=False, missing=["10:30", "11:30", "13:05"])

    assert result.returncode == 42
    payload = json.loads((tmp_path / "audit.json").read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in payload["checks"]}
    assert payload["status"] == "blocked"
    assert by_id["d5.full_trading_day_observation"]["status"] == "observation_required"
    assert by_id["d5.scheduler_embed_cutover"]["status"] == "blocked"
    assert "10:30,11:30,13:05" in by_id["d5.full_trading_day_observation"]["evidence"]
    markdown = (tmp_path / "audit.md").read_text(encoding="utf-8")
    assert "No deployment or cutover" in markdown


def test_remaining_audit_reports_guarded_open_items_after_d5_ready(tmp_path: Path) -> None:
    result = run_audit(tmp_path, d5_ready=True)

    assert result.returncode == 0, result.stderr
    payload = json.loads((tmp_path / "audit.json").read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in payload["checks"]}
    assert payload["status"] == "open_items"
    assert by_id["d5.full_trading_day_observation"]["status"] == "complete"
    assert by_id["d5.scheduler_embed_cutover"]["status"] == "needs_authorization"
    assert by_id["legacy_frontend.retirement_guard"]["status"] == "complete"
    assert by_id["optional_workers.on_demand_runbook"]["status"] == "complete"
    assert by_id["data_quality_sla.non_core_requeue"]["status"] == "complete"


def test_remaining_audit_source_is_read_only_and_non_destructive() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "subprocess.run" not in script
    assert "os.system" not in script
    assert "paramiko" not in script
    assert "ssh " not in script.lower()
    assert "docker compose" not in script
    assert "DELETE FROM" not in script
    assert "UPDATE " not in script
    assert "DROP TABLE" not in script
    assert "systemctl" not in script


def test_remaining_audit_build_function_can_be_imported() -> None:
    module = runpy.run_path(str(SCRIPT))

    assert callable(module["build_audit"])
