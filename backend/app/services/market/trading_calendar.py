from __future__ import annotations

from datetime import date, timedelta


_KNOWN_CN_MARKET_HOLIDAYS = {
    # 2025
    date(2025, 1, 1),
    *[date(2025, 1, day) for day in range(28, 32)],
    *[date(2025, 2, day) for day in range(1, 5)],
    *[date(2025, 4, day) for day in range(4, 7)],
    *[date(2025, 5, day) for day in range(1, 6)],
    *[date(2025, 5, day) for day in range(31, 32)],
    date(2025, 6, 2),
    *[date(2025, 10, day) for day in range(1, 9)],
    # 2026
    date(2026, 1, 1),
    *[date(2026, 2, day) for day in range(16, 23)],
    *[date(2026, 4, day) for day in range(4, 7)],
    *[date(2026, 5, day) for day in range(1, 6)],
    *[date(2026, 6, day) for day in range(19, 22)],
    *[date(2026, 9, day) for day in range(25, 28)],
    *[date(2026, 10, day) for day in range(1, 8)],
    # 2027
    date(2027, 1, 1),
    *[date(2027, 2, day) for day in range(5, 12)],
    *[date(2027, 4, day) for day in range(3, 6)],
    *[date(2027, 5, day) for day in range(1, 6)],
    *[date(2027, 6, day) for day in range(9, 12)],
    *[date(2027, 9, day) for day in range(22, 25)],
    *[date(2027, 10, day) for day in range(1, 8)],
}


def is_a_share_trading_day(value: date) -> bool:
    if value.weekday() >= 5:
        return False
    if _is_chinese_calendar_holiday(value):
        return False
    return value not in _KNOWN_CN_MARKET_HOLIDAYS


def next_a_share_trading_day(value: date) -> date:
    next_day = value + timedelta(days=1)
    while not is_a_share_trading_day(next_day):
        next_day += timedelta(days=1)
    return next_day


def last_a_share_trading_day(value: date | None = None) -> date:
    current = value or date.today()
    while not is_a_share_trading_day(current):
        current -= timedelta(days=1)
    return current


def _is_chinese_calendar_holiday(value: date) -> bool:
    try:
        import chinese_calendar  # type: ignore
    except Exception:
        return False
    try:
        return bool(chinese_calendar.is_holiday(value))
    except Exception:
        return False
