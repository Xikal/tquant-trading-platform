from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MonitorSnapshotResponse(BaseModel):
    updated_at: str
    watchlist_signals: list[dict[str, Any]] = Field(default_factory=list)
    priority_board: dict[str, Any] = Field(default_factory=dict)
