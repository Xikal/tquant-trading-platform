from __future__ import annotations

from pathlib import Path

from scripts.run_focus_strategy_purged_gap_rerun import _command_argv, _expected_json_path


def test_purged_gap_rerun_manifest_commands_are_structured_argv() -> None:
    command = (
        "PYTHONPATH=backend backend/.venv/bin/python backend/scripts/low_buy_execution_matrix.py "
        "--matrix-output-dir backend/data/reports/execution_matrix --states confirmed "
        "--strategies volume_shrink --start 2025-01-01 --end 2026-01-01"
    )

    argv = _command_argv(command)

    assert argv[0].endswith("python")
    assert "backend/scripts/low_buy_execution_matrix.py" in argv
    assert "PYTHONPATH=backend" not in argv


def test_purged_gap_rerun_rejects_shell_metacharacters() -> None:
    command = (
        "PYTHONPATH=backend backend/.venv/bin/python backend/scripts/low_buy_execution_matrix.py "
        "--matrix-output-dir backend/data/reports/execution_matrix; rm -rf /"
    )

    try:
        _command_argv(command)
    except ValueError:
        return
    raise AssertionError("manifest command with shell metacharacters should be rejected")


def test_purged_gap_expected_output_stays_under_repo() -> None:
    command = (
        "PYTHONPATH=backend backend/.venv/bin/python backend/scripts/low_buy_execution_matrix.py "
        "--matrix-output-dir ../outside --states confirmed --strategies volume_shrink"
    )

    try:
        _expected_json_path(command, root=Path("/repo"))
    except ValueError:
        return
    raise AssertionError("manifest output path outside repo should be rejected")
