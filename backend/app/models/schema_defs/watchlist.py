from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class WatchlistCreate(BaseModel):
    symbol: str
    name: str = ""
    base_position: int = 1000
    available_position: int = 1000
    cost_basis: Optional[float] = None
    memo: str = ""


class WatchlistItemOut(BaseModel):
    symbol: str
    name: str
    base_position: int
    available_position: int
    cost_basis: Optional[float] = None
    memo: str
    created_at: datetime
