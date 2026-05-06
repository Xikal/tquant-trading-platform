from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def beijing_now() -> datetime:
    return datetime.now(BEIJING_TZ)


def beijing_now_string() -> str:
    return beijing_now().strftime("%Y-%m-%d %H:%M:%S")


def beijing_today() -> date:
    return beijing_now().date()


def utc_now() -> datetime:
    """Return an aware UTC timestamp for protocol/security fields."""

    return datetime.now(timezone.utc)


def utc_now_naive() -> datetime:
    """Return UTC without tzinfo for legacy SQLAlchemy DateTime columns."""

    return utc_now().replace(tzinfo=None)
