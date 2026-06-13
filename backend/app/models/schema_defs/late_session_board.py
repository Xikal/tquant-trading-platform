from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class LateSessionSnapshotSlot(str, Enum):
    PREVIEW_1450 = "preview_1450"
    SNAPSHOT_1455 = "snapshot_1455"
    FINAL_1457 = "final_1457"
    LATEST = "latest"


class LateSessionBoardStatus(str, Enum):
    OK = "ok"
    PARTIAL_DATA = "partial_data"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"


class LateSessionItemState(str, Enum):
    LATE_CONFIRMED = "late_confirmed"
    LATE_WATCH = "late_watch"
    LATE_REJECTED = "late_rejected"
    LATE_UNAVAILABLE = "late_unavailable"


class LateSessionDegradationReason(str, Enum):
    BLOCKED_BY_MATERIALIZATION = "blocked_by_materialization"
    QUOTE_UNAVAILABLE = "quote_unavailable"
    MINUTE_DATA_MISSING = "minute_data_missing"
    VWAP_UNAVAILABLE = "vwap_unavailable"
    MARKET_CONTEXT_MISSING = "market_context_missing"
    PARTIAL_DATA = "partial_data"
    REFRESH_QUEUED = "refresh_queued"
    SNAPSHOT_FAILED = "snapshot_failed"
    FINAL_SNAPSHOT_FAILED = "final_snapshot_failed"


class LateSessionBoardItemOut(BaseModel):
    symbol: str
    name: str = ""
    strategy_key: str = ""
    strategy_layer: str = ""
    priority_score: float | None = None
    production_score: float | None = None
    buy_signal_state: str = ""
    late_session_state: LateSessionItemState
    late_session_score: float = 0.0
    late_session_reason: str = ""
    vwap: float | None = None
    latest_price: float | None = None
    above_vwap: bool | None = None
    late_session_strength: bool | None = None
    low_rising: bool | None = None
    risk_tags: list[str] = Field(default_factory=list)
    reject_reasons: list[str] = Field(default_factory=list)
    quote_timestamp: str = ""
    snapshot_slot: LateSessionSnapshotSlot
    source: dict[str, Any] = Field(default_factory=dict)


class LateSessionBoardResponse(BaseModel):
    trade_date: str = ""
    snapshot_slot: LateSessionSnapshotSlot
    generated_at: datetime
    source_priority_board_epoch: str = ""
    status: LateSessionBoardStatus
    items: list[LateSessionBoardItemOut] = Field(default_factory=list)
    data_quality: str = ""
    data_quality_tags: list[str] = Field(default_factory=list)
    degradation_reason: str = ""
    next_refresh_at: str = ""
    refresh_mode: str = "cache"
    source: dict[str, Any] = Field(default_factory=dict)
