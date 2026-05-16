from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FactorDefinitionEntity(Base):
    __tablename__ = "factor_definitions"
    __table_args__ = (UniqueConstraint("factor_key", name="uq_factor_definitions_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    factor_key: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    hypothesis: Mapped[str] = mapped_column(Text, default="")
    formula_code: Mapped[str] = mapped_column(Text, default="")
    data_deps_json: Mapped[str] = mapped_column(Text, default="[]")
    direction: Mapped[str] = mapped_column(String(24), default="higher_better")
    category: Mapped[str] = mapped_column(String(40), default="price")
    status: Mapped[str] = mapped_column(String(24), default="candidate", index=True)
    source: Mapped[str] = mapped_column(String(40), default="human_crafted", index=True)
    version: Mapped[str] = mapped_column(String(40), default="v1")
    eval_result_json: Mapped[str] = mapped_column(Text, default="{}")
    created_by: Mapped[str] = mapped_column(String(80), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), index=True
    )


class FactorEvalRunEntity(Base):
    __tablename__ = "factor_eval_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    factor_key: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(24), default="succeeded", index=True)
    start_date: Mapped[str] = mapped_column(String(16), default="", index=True)
    end_date: Mapped[str] = mapped_column(String(16), default="", index=True)
    symbol_count: Mapped[int] = mapped_column(Integer, default=0)
    observation_count: Mapped[int] = mapped_column(Integer, default=0)
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")
    interpretation_json: Mapped[str] = mapped_column(Text, default="{}")
    error_message: Mapped[str] = mapped_column(Text, default="")
    elapsed_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class FactorApprovalEntity(Base):
    __tablename__ = "factor_approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    factor_key: Mapped[str] = mapped_column(String(120), index=True)
    action: Mapped[str] = mapped_column(String(40), default="", index=True)
    from_status: Mapped[str] = mapped_column(String(24), default="")
    to_status: Mapped[str] = mapped_column(String(24), default="")
    operator_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
