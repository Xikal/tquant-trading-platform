from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class DataQualitySnapshotOut(BaseModel):
    dataset_key: str
    as_of_date: date
    scope: str
    expected_days: int
    actual_days: int
    missing_days: int
    invalid_rows: int
    duplicate_rows: int
    stale: bool
    coverage_pct: float
    status: str
    blockers: list[str] = Field(default_factory=list)
    checked_at: datetime | None = None


class DataRepairAuditOut(BaseModel):
    id: int
    repair_id: str
    dataset_key: str
    reason: str
    backup_path: str = ""
    refetch_result: str = ""
    deleted_rows_count: int = 0
    fabricated: bool = False
    operator: str = ""
    created_at: datetime | None = None


class DataQualitySlaResponse(BaseModel):
    items: list[DataQualitySnapshotOut] = Field(default_factory=list)
    latest_repair_audits: list[DataRepairAuditOut] = Field(default_factory=list)
    total: int = 0


class RuntimeFallbackStatusResponse(BaseModel):
    worker_status: Literal["running", "stale", "missing"] | str
    worker_id: str = ""
    heartbeat_updated_at: str = ""
    heartbeat_age_seconds: int | None = None
    critical_queued_count: int = 0
    oldest_critical_queued_at: str = ""
    oldest_critical_queued_age_seconds: int | None = None
    blocking: bool = False
    message: str = ""
    recovery_actions: list[str] = Field(default_factory=list)


class DataQualityMissingSymbolOut(BaseModel):
    symbol: str
    name: str = ""
    missing_days: int = 0


class DataQualityCoverageResponse(BaseModel):
    dataset_key: str
    scope: str
    missing_symbols: list[DataQualityMissingSymbolOut] = Field(default_factory=list)
    missing_dates: list[date] = Field(default_factory=list)


class DataQualityBackfillRequest(BaseModel):
    dataset_key: str = "daily_bars"
    scope: str = "all"
    start_date: date
    end_date: date


class TradeDataGateCheckOut(BaseModel):
    key: str
    label: str
    ok: bool
    severity: Literal["green", "yellow", "red"]
    detail: str = ""


class TradeDataGateResponse(BaseModel):
    ok: bool
    checks: list[TradeDataGateCheckOut] = Field(default_factory=list)


class DataRepairRunRequest(BaseModel):
    dataset_key: str = "daily_bars"
    dry_run: bool = True
    output_path: str = ""
    backup_dir: str = ""
    refetch: bool = True
