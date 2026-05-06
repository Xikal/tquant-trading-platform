from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def beijing_now() -> datetime:
    return datetime.now(BEIJING_TZ)


def beijing_now_string() -> str:
    return beijing_now().strftime("%Y-%m-%d %H:%M:%S")


def beijing_today() -> date:
    return beijing_now().date()
