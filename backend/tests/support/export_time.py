from __future__ import annotations

from datetime import date, datetime, time, timedelta

EXPORT_WINDOW_END_DATE = date(2026, 6, 8)


def export_window_date(offset_days: int = 0) -> date:
    return EXPORT_WINDOW_END_DATE + timedelta(days=offset_days)


def export_window_datetime(offset_days: int = 0, *, hour: int = 16, minute: int = 0, second: int = 0) -> datetime:
    # Window-sensitive export fixtures must not depend on DB defaults or wall-clock time.
    return datetime.combine(export_window_date(offset_days), time(hour, minute, second))
