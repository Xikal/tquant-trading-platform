from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "scripts" / "plan_analytics_manifest_exports.py"


def run_plan(report_path: Path, tmp_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest-report",
            str(report_path),
            "--analytics-root",
            "/host/analytics",
            "--task-output-root",
            "/container/analytics",
            "--end-date",
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


def test_export_plan_maps_missing_manifests_to_low_priority_tasks(tmp_path: Path) -> None:
    report = {
        "datasets": {
            "daily_bars": {
                "dataset_key": "daily_bars",
                "present": True,
                "row_count": 2443775,
                "quality_status": "ok",
                "warnings": ["manifest_id_missing"],
                "blockers": [],
            },
            "strategy_tracking_snapshots": {
                "dataset_key": "strategy_tracking_snapshots",
                "present": False,
                "warnings": [],
                "blockers": ["manifest_missing"],
            },
            "backtest_runs": {
                "dataset_key": "backtest_runs",
                "present": False,
                "warnings": [],
                "blockers": ["manifest_missing"],
            },
        }
    }
    report_path = tmp_path / "manifest-report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    result = run_plan(report_path, tmp_path, "--fail-on-blocking")

    assert result.returncode == 42
    plan = json.loads((tmp_path / "plan.json").read_text(encoding="utf-8"))
    assert plan["dry_run_only"] is True
    assert plan["safety"]["does_enqueue_tasks"] is False
    assert plan["safety"]["does_run_exporters"] is False
    assert plan["safety"]["does_modify_mysql"] is False
    assert plan["summary"]["ready_count"] == 1
    assert plan["summary"]["optional_refresh_count"] == 1
    assert plan["summary"]["export_required_count"] == 9
    assert plan["summary"]["required_task_count"] == 9
    tasks = {item["dataset_key"]: item for item in plan["actions"]}
    assert tasks["strategy_tracking_snapshots"]["task_type"] == "analytics_export_strategy_tracking_snapshots"
    assert tasks["strategy_tracking_snapshots"]["payload"] == {
        "days": 90,
        "end_date": "2026-06-08",
        "output_root": "/container/analytics",
        "source": "platform_analytics_manifest_export_plan",
        "idempotency_key": "analytics-export:strategy_tracking_snapshots:2026-06-08",
    }
    assert tasks["backtest_runs"]["payload"]["days"] == 180
    assert tasks["daily_bars"]["action"] == "lifecycle_refresh_optional"

    markdown = (tmp_path / "plan.md").read_text(encoding="utf-8")
    assert "dry-run 报告" in markdown
    assert "analytics_export_strategy_tracking_snapshots" in markdown


def test_export_plan_marks_hash_mismatch_as_reexport(tmp_path: Path) -> None:
    report_path = tmp_path / "manifest-report.json"
    report_path.write_text(
        json.dumps(
            {
                "datasets": {
                    "daily_bars": {
                        "dataset_key": "daily_bars",
                        "present": True,
                        "warnings": [],
                        "blockers": ["artifact_hash_mismatch:1"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = run_plan(report_path, tmp_path)

    assert result.returncode == 0
    plan = json.loads((tmp_path / "plan.json").read_text(encoding="utf-8"))
    actions = {item["dataset_key"]: item for item in plan["actions"]}
    assert actions["daily_bars"]["action"] == "reexport_required"
    assert actions["daily_bars"]["payload"]["months"] == 24
    assert "manifest_reexport_required_count=1" in plan["evaluation"]["blocking"]


def test_export_plan_accepts_list_dataset_shape(tmp_path: Path) -> None:
    report_path = tmp_path / "manifest-report.json"
    report_path.write_text(
        json.dumps(
            {
                "datasets": [
                    {
                        "dataset_key": "daily_bars",
                        "present": True,
                        "warnings": [],
                        "blockers": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = run_plan(report_path, tmp_path)

    assert result.returncode == 0
    plan = json.loads((tmp_path / "plan.json").read_text(encoding="utf-8"))
    actions = {item["dataset_key"]: item for item in plan["actions"]}
    assert actions["daily_bars"]["action"] == "ready"
    assert plan["summary"]["export_required_count"] == 9


def test_export_plan_source_is_report_only_and_non_destructive() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "DELETE FROM" not in script
    assert "UPDATE " not in script
    assert "DROP TABLE" not in script
    assert "PURGE BINARY LOGS" not in script
    assert "docker volume prune" not in script
    assert "subprocess.run" not in script
    assert "requests." not in script
    assert "SessionLocal" not in script
