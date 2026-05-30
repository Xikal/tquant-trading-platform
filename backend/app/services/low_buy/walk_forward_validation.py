from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from app.services.low_buy.front_row_weighted_validation_config import (
    WALK_FORWARD_MIN_PASS_RATE_PCT,
    WALK_FORWARD_MIN_WINDOWS,
)


@dataclass(frozen=True)
class WalkForwardWindow:
    window_id: int
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    purged_gap_start: str
    purged_gap_end: str
    oos_start: str
    oos_end: str
    oos_trade_days: int
    split_order: str = "train_validation_purged_gap_oos"

    def as_dict(self) -> dict[str, Any]:
        return {
            "window_id": self.window_id,
            "train_start": self.train_start,
            "train_end": self.train_end,
            "validation_start": self.validation_start,
            "validation_end": self.validation_end,
            "purged_gap_start": self.purged_gap_start,
            "purged_gap_end": self.purged_gap_end,
            "oos_start": self.oos_start,
            "oos_end": self.oos_end,
            "oos_trade_days": self.oos_trade_days,
            "split_order": self.split_order,
        }


def generate_walk_forward_windows(
    trade_dates: list[str],
    *,
    train_months: int,
    validation_months: int,
    purged_gap_days: int,
    oos_trade_days: int,
    step_trade_days: int,
) -> list[WalkForwardWindow]:
    dates = sorted(str(item) for item in trade_dates if str(item or "").strip())
    windows: list[WalkForwardWindow] = []
    if not dates:
        return windows
    start_index = 0
    while start_index < len(dates):
        train_start = dates[start_index]
        train_end_limit = _add_months(date.fromisoformat(train_start), train_months) - timedelta(days=1)
        train_end_index = _last_index_on_or_before(dates, train_end_limit.isoformat())
        if train_end_index is None or train_end_index <= start_index:
            break
        validation_start_index = train_end_index + 1
        if validation_start_index >= len(dates):
            break
        validation_start = dates[validation_start_index]
        validation_end_limit = _add_months(date.fromisoformat(validation_start), validation_months) - timedelta(days=1)
        validation_end_index = _last_index_on_or_before(dates, validation_end_limit.isoformat())
        if validation_end_index is None or validation_end_index < validation_start_index:
            break
        purge_start_index = validation_end_index + 1
        purge_end_index = purge_start_index + max(purged_gap_days, 0) - 1
        oos_start_index = purge_end_index + 1
        oos_end_index = oos_start_index + max(oos_trade_days, 1) - 1
        if oos_end_index >= len(dates):
            break
        windows.append(
            WalkForwardWindow(
                window_id=len(windows) + 1,
                train_start=train_start,
                train_end=dates[train_end_index],
                validation_start=validation_start,
                validation_end=dates[validation_end_index],
                purged_gap_start=dates[purge_start_index] if purge_start_index < len(dates) else "",
                purged_gap_end=dates[purge_end_index] if purge_end_index < len(dates) and purged_gap_days > 0 else "",
                oos_start=dates[oos_start_index],
                oos_end=dates[oos_end_index],
                oos_trade_days=oos_trade_days,
            )
        )
        start_index += max(step_trade_days, 1)
    return windows


def walk_forward_overall_decision(window_rows: list[dict[str, Any]]) -> dict[str, Any]:
    window_count = len(window_rows)
    passed_count = sum(1 for item in window_rows if bool(item.get("passed")))
    pass_rate = round(passed_count / max(window_count, 1) * 100.0, 4)
    blockers: list[str] = []
    if window_count < WALK_FORWARD_MIN_WINDOWS:
        blockers.append("walk_forward_window_count_below_6")
    if pass_rate < WALK_FORWARD_MIN_PASS_RATE_PCT:
        blockers.append("walk_forward_pass_rate_below_70pct")
    if _has_two_consecutive_failures(window_rows):
        blockers.append("walk_forward_two_consecutive_failed_windows")
    return {
        "window_count": window_count,
        "passed_window_count": passed_count,
        "passed_window_rate_pct": pass_rate,
        "no_two_consecutive_failed_windows": not _has_two_consecutive_failures(window_rows),
        "passed": not blockers,
        "blockers": blockers,
    }


def _add_months(value: date, months: int) -> date:
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    days_by_month = [31, 29 if _is_leap_year(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return date(year, month, min(value.day, days_by_month[month - 1]))


def _is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _last_index_on_or_before(dates: list[str], limit: str) -> int | None:
    result: int | None = None
    for index, item in enumerate(dates):
        if item <= limit:
            result = index
        else:
            break
    return result


def _has_two_consecutive_failures(rows: list[dict[str, Any]]) -> bool:
    failed_streak = 0
    for row in rows:
        if bool(row.get("passed")):
            failed_streak = 0
            continue
        failed_streak += 1
        if failed_streak >= 2:
            return True
    return False
