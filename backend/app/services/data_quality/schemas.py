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
