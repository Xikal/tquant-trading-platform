from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class TrackRecordDriftItemOut(BaseModel):
    strategy_key: str
    as_of_date: date
    window_days: int
    realized_pf: float | None = None
    expected_pf: float | None = None
    realized_avg: float = 0.0
    expected_avg: float = 0.0
    realized_winrate: float = 0.0
    expected_winrate: float = 0.0
    realized_max5: float = 0.0
    backtest_max5: float = 0.0
    realized_max10: float = 0.0
    backtest_max10: float = 0.0
    tracking_error: float = 0.0
    decay_pct: float = 0.0
    drift_flag: str = "insufficient_sample"
    sample_settled: int = 0
    created_at: datetime | None = None


class TrackRecordDriftResponse(BaseModel):
    items: list[TrackRecordDriftItemOut] = Field(default_factory=list)
    total: int = 0
    data_quality: str = "ok"


class TrackRecordLedgerItemOut(BaseModel):
    id: int
    signal_date: date
    strategy_key: str
    symbol: str
    name: str = ""
    signal_state: str
    production_score: float | None = None
    priority_score: float = 0.0
    data_quality: str = "unknown"
    signal_time: datetime
    data_cutoff_time: datetime
    return_start_time: datetime
    source_version: str = ""


class TrackRecordLedgerResponse(BaseModel):
    items: list[TrackRecordLedgerItemOut] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0
