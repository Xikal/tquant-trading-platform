from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DecisionContextSnapshot(Base):
    __tablename__ = "decision_context_snapshots"
    __table_args__ = (
        UniqueConstraint("trade_date", "strategy_key", "symbol", name="uq_decision_context_day_strategy_symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    strategy_key: Mapped[str] = mapped_column(String(80), index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    strategy_tier: Mapped[str] = mapped_column(String(20), default="research", index=True)
    production_eligible: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    final_decision: Mapped[str] = mapped_column(String(24), default="watch", index=True)
    final_score: Mapped[float] = mapped_column(Float, default=0.0)
    data_quality: Mapped[str] = mapped_column(String(24), default="missing", index=True)
    gates_json: Mapped[str] = mapped_column(Text, default="{}")
    evidence_json: Mapped[str] = mapped_column(Text, default="{}")
    source_snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), index=True)


class SignalOutcomeAttribution(Base):
    __tablename__ = "signal_outcome_attributions"
    __table_args__ = (
        UniqueConstraint("context_snapshot_id", "horizon_days", name="uq_signal_outcome_context_horizon"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    context_snapshot_id: Mapped[int] = mapped_column(ForeignKey("decision_context_snapshots.id"), index=True)
    horizon_days: Mapped[int] = mapped_column(Integer, index=True)
    return_pct: Mapped[float] = mapped_column(Float, default=0.0)
    max_gain_pct: Mapped[float] = mapped_column(Float, default=0.0)
    max_drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)
    hit: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    exit_reason: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class StrategyPromotionReview(Base):
    __tablename__ = "strategy_promotion_reviews"
    __table_args__ = (
        UniqueConstraint("strategy_key", "review_date", "window_days", name="uq_strategy_promotion_review_window"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    strategy_key: Mapped[str] = mapped_column(String(80), index=True)
    review_date: Mapped[date] = mapped_column(Date, index=True)
    window_days: Mapped[int] = mapped_column(Integer, index=True)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    profit_factor: Mapped[float] = mapped_column(Float, default=0.0)
    average_trade_pct: Mapped[float] = mapped_column(Float, default=0.0)
    max_drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)
    max5_return_pct: Mapped[float] = mapped_column(Float, default=0.0)
    max10_return_pct: Mapped[float] = mapped_column(Float, default=0.0)
    quarterly_stability: Mapped[float] = mapped_column(Float, default=0.0)
    walk_forward_pass: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    oos_pass: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    recommendation: Mapped[str] = mapped_column(String(32), default="stay_research", index=True)
    evidence_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
