from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.sqlalchemy_types import FlexibleDate


class DataQualitySnapshot(Base):
    __tablename__ = "data_quality_snapshots"
    __table_args__ = (
        UniqueConstraint("dataset_key", "as_of_date", "scope", name="uq_data_quality_snapshot_dataset_scope_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_key: Mapped[str] = mapped_column(String(64), index=True)
    as_of_date: Mapped[date] = mapped_column(FlexibleDate(), index=True)
    scope: Mapped[str] = mapped_column(String(40), index=True)
    expected_days: Mapped[int] = mapped_column(Integer, default=0)
    actual_days: Mapped[int] = mapped_column(Integer, default=0)
    missing_days: Mapped[int] = mapped_column(Integer, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_rows: Mapped[int] = mapped_column(Integer, default=0)
    stale: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    coverage_pct: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(24), default="unknown", index=True)
    blockers_json: Mapped[str] = mapped_column(Text, default="[]")
    checked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class DataRepairAudit(Base):
    __tablename__ = "data_repair_audits"
    __table_args__ = (
        UniqueConstraint("repair_id", name="uq_data_repair_audit_repair_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repair_id: Mapped[str] = mapped_column(String(80), index=True)
    dataset_key: Mapped[str] = mapped_column(String(64), index=True)
    reason: Mapped[str] = mapped_column(String(120), index=True)
    detected_rows_json: Mapped[str] = mapped_column(Text, default="[]")
    backup_path: Mapped[str] = mapped_column(Text, default="")
    refetch_result: Mapped[str] = mapped_column(Text, default="")
    deleted_rows_json: Mapped[str] = mapped_column(Text, default="[]")
    fabricated: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    operator: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
