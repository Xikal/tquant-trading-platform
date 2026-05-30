from __future__ import annotations

from datetime import date, timedelta

from app.services.low_buy.walk_forward_validation import generate_walk_forward_windows, walk_forward_overall_decision


def _trade_dates(start: str, count: int) -> list[str]:
    current = date.fromisoformat(start)
    dates: list[str] = []
    while len(dates) < count:
        if current.weekday() < 5:
            dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates


def test_walk_forward_windows_are_time_ordered_with_purged_gap() -> None:
    windows = generate_walk_forward_windows(
        _trade_dates("2024-01-02", 520),
        train_months=12,
        validation_months=3,
        purged_gap_days=10,
        oos_trade_days=60,
        step_trade_days=20,
    )

    assert windows
    first = windows[0].as_dict()
    assert first["train_start"] < first["train_end"] < first["validation_start"] < first["validation_end"]
    assert first["validation_end"] < first["purged_gap_start"] <= first["purged_gap_end"] < first["oos_start"] < first["oos_end"]
    assert first["oos_trade_days"] == 60
    assert first["split_order"] == "train_validation_purged_gap_oos"


def test_walk_forward_overall_blocks_insufficient_windows_and_pass_rate() -> None:
    result = walk_forward_overall_decision([{"passed": False}, {"passed": False}])

    assert not result["passed"]
    assert "walk_forward_window_count_below_6" in result["blockers"]
    assert "walk_forward_pass_rate_below_70pct" in result["blockers"]
    assert "walk_forward_two_consecutive_failed_windows" in result["blockers"]
