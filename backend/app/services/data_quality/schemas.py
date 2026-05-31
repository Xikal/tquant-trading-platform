from __future__ import annotations

from datetime import date, datetime

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


class DataRepairRunRequest(BaseModel):
    dataset_key: str = "daily_bars"
    dry_run: bool = True
    output_path: str = ""
    backup_dir: str = ""
    refetch: bool = True
