from __future__ import annotations

from datetime import datetime

from app.runtime.background_jobs import _ml_incremental_train_due


def test_ml_incremental_train_runs_after_friday_close() -> None:
    assert _ml_incremental_train_due(datetime(2026, 5, 15, 16, 0)) is True
    assert _ml_incremental_train_due(datetime(2026, 5, 15, 15, 59)) is False


def test_ml_incremental_train_does_not_run_on_monday() -> None:
    assert _ml_incremental_train_due(datetime(2026, 5, 11, 16, 30)) is False
