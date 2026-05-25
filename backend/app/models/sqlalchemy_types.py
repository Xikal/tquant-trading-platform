from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Date
from sqlalchemy.types import TypeDecorator


class FlexibleDate(TypeDecorator[date]):
    """DATE column that still accepts existing ISO date strings from callers."""

    impl = Date
    cache_ok = True

    def process_bind_param(self, value: Any, dialect) -> date | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            clean = value.strip()
            if not clean:
                return None
            return date.fromisoformat(clean[:10])
        return value
