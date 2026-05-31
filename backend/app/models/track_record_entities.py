from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.sqlalchemy_types import FlexibleDate


class ProductionSignalLedger(Base):
    __tablename__ = "production_signal_ledger"
    __table_args__ = (
        UniqueConstraint("signal_date", "strategy_key", "symbol", name="uq_production_signal_ledger_signal"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_date: Mapped[date] = mapped_column(FlexibleDate(), index=True)
    strategy_key: Mapped[str] = mapped_column(String(80), index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    signal_state: Mapped[str] = mapped_column(String(24), index=True)
    production_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    entry_zone_low: Mapped[float] = mapped_column(Float, default=0.0)
    entry_zone_high: Mapped[float] = mapped_column(Float, default=0.0)
    stop_loss: Mapped[float] = mapped_column(Float, default=0.0)
    expected_horizon_returns_json: Mapped[str] = mapped_column(Text, default="{}")
    market_regime: Mapped[str] = mapped_column(String(40), default="", index=True)
    front_row_tier: Mapped[str] = mapped_column(String(40), default="", index=True)
    data_quality: Mapped[str] = mapped_column(String(40), default="unknown", index=True)
    signal_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    data_cutoff_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    return_start_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    source_version: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class SignalRealizedOutcome(Base):
    __tablename__ = "signal_realized_outcomes"
    __table_args__ = (
        UniqueConstraint("ledger_id", "horizon_days", name="uq_signal_realized_outcome_ledger_horizon"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ledger_id: Mapped[int] = mapped_column(ForeignKey("production_signal_ledger.id"), index=True)
    horizon_days: Mapped[int] = mapped_column(Integer, index=True)
    return_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_gain_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_drawdown_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str] = mapped_column(String(80), default="")
    return_start_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    settled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    data_quality: Mapped[str] = mapped_column(String(40), default="unknown", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class StrategyDriftSnapshot(Base):
    __tablename__ = "strategy_drift_snapshots"
    __table_args__ = (
        UniqueConstraint("strategy_key", "as_of_date", "window_days", name="uq_strategy_drift_snapshot_key_window"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    strategy_key: Mapped[str] = mapped_column(String(80), index=True)
    as_of_date: Mapped[date] = mapped_column(FlexibleDate(), index=True)
    window_days: Mapped[int] = mapped_column(Integer, index=True)
    realized_pf: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    expected_pf: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    realized_avg: Mapped[float] = mapped_column(Float, default=0.0)
    expected_avg: Mapped[float] = mapped_column(Float, default=0.0)
    realized_winrate: Mapped[float] = mapped_column(Float, default=0.0)
    expected_winrate: Mapped[float] = mapped_column(Float, default=0.0)
    realized_max5: Mapped[float] = mapped_column(Float, default=0.0)
    backtest_max5: Mapped[float] = mapped_column(Float, default=0.0)
    realized_max10: Mapped[float] = mapped_column(Float, default=0.0)
    backtest_max10: Mapped[float] = mapped_column(Float, default=0.0)
    tracking_error: Mapped[float] = mapped_column(Float, default=0.0)
    decay_pct: Mapped[float] = mapped_column(Float, default=0.0)
    drift_flag: Mapped[str] = mapped_column(String(40), default="insufficient_sample", index=True)
    sample_settled: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
