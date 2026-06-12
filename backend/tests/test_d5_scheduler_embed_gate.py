from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "scripts" / "verify_d5_scheduler_embed_gate.py"


def run_gate(summary_path: Path, fail_on_blocked: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = ["python3", str(SCRIPT), "--summary", str(summary_path)]
    if fail_on_blocked:
        cmd.append("--fail-on-blocked")
    return subprocess.run(cmd, cwd=ROOT_DIR, text=True, capture_output=True, check=False)


def write_summary(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_gate_blocks_incomplete_d5_summary(tmp_path: Path) -> None:
    summary_path = write_summary(
        tmp_path,
        {
            "checkpoint_count": 3,
            "required_checkpoints": ["09:15", "09:35", "10:30"],
            "observed_checkpoints": ["09:15", "09:35"],
            "missing_checkpoints": ["10:30"],
            "full_trading_day_complete": False,
            "d5_ready": False,
            "d5_blockers": ["full_trading_day_observation_incomplete"],
        },
    )

    result = run_gate(summary_path)
    payload = json.loads(result.stdout)

    assert result.returncode == 42
    assert payload["status"] == "blocked"
    assert "d5_ready=false" in payload["blocking"]
    assert "full_trading_day_complete=false" in payload["blocking"]
    assert "missing_checkpoints=10:30" in payload["blocking"]
    assert "d5_blocker=full_trading_day_observation_incomplete" in payload["blocking"]


def test_gate_allows_ready_d5_summary(tmp_path: Path) -> None:
    summary_path = write_summary(
        tmp_path,
        {
            "checkpoint_count": 8,
            "required_checkpoints": ["09:15", "09:35"],
            "observed_checkpoints": ["09:15", "09:35"],
            "missing_checkpoints": [],
            "full_trading_day_complete": True,
            "d5_ready": True,
            "d5_blockers": [],
        },
    )

    result = run_gate(summary_path)
    payload = json.loads(result.stdout)

    assert result.returncode == 0
    assert payload["ok"] is True
    assert payload["status"] == "ready"
    assert payload["blocking"] == []


def test_gate_blocks_missing_summary_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.json"

    result = run_gate(missing_path)
    payload = json.loads(result.stdout)

    assert result.returncode == 42
    assert payload["status"] == "blocked"
    assert payload["blocking"] == [f"summary_not_found={missing_path}"]
