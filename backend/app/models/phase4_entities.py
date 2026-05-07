from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RuntimeTask(Base):
    """Durable background task record used by the standalone runtime worker."""

    __tablename__ = "runtime_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_type: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), default="", index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    error_message: Mapped[str] = mapped_column(Text, default="")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0)
    locked_by: Mapped[str] = mapped_column(String(80), default="", index=True)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    run_after: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), index=True
    )


class RuntimeTaskEvent(Base):
    """Append-only event stream for task progress and SSE/WebSocket consumers."""

    __tablename__ = "runtime_task_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer, index=True)
    event_type: Mapped[str] = mapped_column(String(40), default="progress", index=True)
    message: Mapped[str] = mapped_column(String(240), default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class AgentResultQuality(Base):
    """Structured quality score for Hermes/Agent results before user delivery."""

    __tablename__ = "agent_result_quality"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(80), default="", index=True)
    provider: Mapped[str] = mapped_column(String(40), default="", index=True)
    agent_id: Mapped[str] = mapped_column(String(80), default="", index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    issue_count: Mapped[int] = mapped_column(Integer, default=0)
    issues_json: Mapped[str] = mapped_column(Text, default="[]")
    input_summary: Mapped[str] = mapped_column(Text, default="")
    output_summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class QuantParameterSet(Base):
    """Versioned strategy and risk parameters for reproducible research/backtests."""

    __tablename__ = "quant_parameter_sets"
    __table_args__ = (
        UniqueConstraint("version", name="uq_quant_parameter_sets_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    scope: Mapped[str] = mapped_column(String(40), default="low_buy", index=True)
    params_json: Mapped[str] = mapped_column(Text, default="{}")
    description: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(80), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class QuantParameterAuditLog(Base):
    """Append-only audit log for quant parameter changes."""

    __tablename__ = "quant_parameter_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(40), default="", index=True)
    version: Mapped[str] = mapped_column(String(80), default="", index=True)
    scope: Mapped[str] = mapped_column(String(40), default="global", index=True)
    operator: Mapped[str] = mapped_column(String(80), default="")
    before_json: Mapped[str] = mapped_column(Text, default="{}")
    after_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class MLSignalSample(Base):
    """Training sample store for future XGBoost/LightGBM signal models."""

    __tablename__ = "ml_signal_samples"
    __table_args__ = (
        UniqueConstraint("sample_key", name="uq_ml_signal_samples_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sample_key: Mapped[str] = mapped_column(String(160), index=True)
    symbol: Mapped[str] = mapped_column(String(16), default="", index=True)
    trade_date: Mapped[str] = mapped_column(String(16), default="", index=True)
    strategy_key: Mapped[str] = mapped_column(String(80), default="", index=True)
    feature_json: Mapped[str] = mapped_column(Text, default="{}")
    label_json: Mapped[str] = mapped_column(Text, default="{}")
    source: Mapped[str] = mapped_column(String(40), default="paper", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class MLSignalModel(Base):
    """Model registry entry. First phase keeps models research-only."""

    __tablename__ = "ml_signal_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    model_type: Mapped[str] = mapped_column(String(40), default="heuristic")
    status: Mapped[str] = mapped_column(String(24), default="research", index=True)
    feature_schema_json: Mapped[str] = mapped_column(Text, default="{}")
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")
    artifact_uri: Mapped[str] = mapped_column(String(300), default="")
    remote_artifact_uri: Mapped[str] = mapped_column(String(500), default="")
    artifact_checksum: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class PaperBacktestComparison(Base):
    """Daily comparison between expected backtest metrics and paper trading results."""

    __tablename__ = "paper_backtest_comparisons"
    __table_args__ = (
        UniqueConstraint("account_id", "backtest_run_id", "comparison_date", name="uq_paper_backtest_compare"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(Integer, index=True)
    backtest_run_id: Mapped[int] = mapped_column(Integer, index=True)
    comparison_date: Mapped[date] = mapped_column(Date, index=True)
    expected_return_pct: Mapped[float] = mapped_column(Float, default=0.0)
    actual_return_pct: Mapped[float] = mapped_column(Float, default=0.0)
    deviation_pct: Mapped[float] = mapped_column(Float, default=0.0)
    alert: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    reason: Mapped[str] = mapped_column(String(240), default="")
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
