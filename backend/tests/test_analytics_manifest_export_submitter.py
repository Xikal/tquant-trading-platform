from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "scripts" / "submit_analytics_manifest_exports.py"


def _load_submitter():
    spec = importlib.util.spec_from_file_location("submit_analytics_manifest_exports", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_submitter(plan_path: Path, tmp_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--export-plan",
            str(plan_path),
            "--json-output",
            str(tmp_path / "submission.json"),
            "--markdown-output",
            str(tmp_path / "submission.md"),
            *extra,
        ],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )


def test_submitter_dry_run_selects_required_exports_without_enqueue(tmp_path: Path) -> None:
    plan_path = _write_export_plan(tmp_path)

    result = run_submitter(plan_path, tmp_path)

    assert result.returncode == 0
    payload = json.loads((tmp_path / "submission.json").read_text(encoding="utf-8"))
    assert payload["mode"] == "dry-run"
    assert payload["safety"]["writes_runtime_tasks_only_when_apply"] is False
    assert payload["summary"]["selected_task_count"] == 2
    assert "submitted" not in payload
    assert payload["tasks"][0]["priority"] == 900
    markdown = (tmp_path / "submission.md").read_text(encoding="utf-8")
    assert "默认 dry-run" in markdown


def test_submitter_filters_dataset_and_includes_optional_refresh(tmp_path: Path) -> None:
    plan_path = _write_export_plan(tmp_path)

    result = run_submitter(
        plan_path,
        tmp_path,
        "--include-optional-refresh",
        "--datasets",
        "daily_bars,backtest_runs",
        "--priority",
        "950",
    )

    assert result.returncode == 0
    payload = json.loads((tmp_path / "submission.json").read_text(encoding="utf-8"))
    assert payload["summary"]["selected_datasets"] == ["daily_bars", "backtest_runs"]
    assert [task["priority"] for task in payload["tasks"]] == [950, 950]


def test_submitter_apply_requires_explicit_confirm(tmp_path: Path) -> None:
    plan_path = _write_export_plan(tmp_path)

    result = run_submitter(plan_path, tmp_path, "--apply")

    assert result.returncode == 64
    payload = json.loads((tmp_path / "submission.json").read_text(encoding="utf-8"))
    assert payload["evaluation"]["status"] == "blocked"
    assert payload["evaluation"]["blocking"] == ["confirm_apply_required"]


def test_submit_tasks_uses_injected_enqueue_function() -> None:
    module = _load_submitter()
    report = {
        "summary": {"selected_task_count": 1},
        "evaluation": {"status": "ready_to_submit", "warnings": [], "blocking": []},
        "tasks": [
            {
                "dataset_key": "backtest_runs",
                "task_type": "analytics_export_backtest_runs",
                "idempotency_key": "analytics-export:backtest_runs:2026-06-08",
                "payload": {"days": 180},
            }
        ],
    }
    calls = []

    def fake_enqueue(task):
        calls.append(task)
        return {"dataset_key": task["dataset_key"], "task_type": task["task_type"], "task_id": 7, "status": "queued"}

    submitted = module.submit_tasks(report, fake_enqueue)

    assert len(calls) == 1
    assert submitted["summary"]["submitted_task_count"] == 1
    assert submitted["evaluation"]["status"] == "submitted"
    assert submitted["submitted"][0]["task_id"] == 7


def test_submitter_source_is_runtime_task_only_and_non_destructive() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "DELETE FROM" not in script
    assert "UPDATE " not in script
    assert "DROP TABLE" not in script
    assert "PURGE BINARY LOGS" not in script
    assert "docker volume prune" not in script
    assert "rm -rf" not in script
    assert "export_daily_bars_parquet" not in script
    assert "export_strategy_tracking_snapshots_parquet" not in script
    assert "RuntimeTaskWorker" not in script
    assert "register_analytics_handlers" not in script
    assert "RuntimeTaskQueue" in script


def _write_export_plan(tmp_path: Path) -> Path:
    plan = {
        "actions": [
            {
                "dataset_key": "daily_bars",
                "action": "lifecycle_refresh_optional",
                "task_type": "analytics_export_daily_bars",
                "payload": {
                    "months": 24,
                    "end_date": "2026-06-08",
                    "output_root": "/analytics",
                    "idempotency_key": "analytics-export:daily_bars:2026-06-08",
                },
            },
            {
                "dataset_key": "strategy_tracking_snapshots",
                "action": "export_required",
                "task_type": "analytics_export_strategy_tracking_snapshots",
                "payload": {
                    "days": 90,
                    "end_date": "2026-06-08",
                    "output_root": "/analytics",
                    "idempotency_key": "analytics-export:strategy_tracking_snapshots:2026-06-08",
                },
            },
            {
                "dataset_key": "backtest_runs",
                "action": "export_required",
                "task_type": "analytics_export_backtest_runs",
                "payload": {
                    "days": 180,
                    "end_date": "2026-06-08",
                    "output_root": "/analytics",
                    "idempotency_key": "analytics-export:backtest_runs:2026-06-08",
                },
            },
        ]
    }
    path = tmp_path / "export-plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path
