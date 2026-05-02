from __future__ import annotations

from typing import Any


def paper_trade_enabled(value: Any) -> bool:
    """Treat legacy NULL as enabled, but respect explicit false/0 values."""

    if value is None:
        return True
    return bool(value)
