from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LowBuyPoolSnapshot(Base):
    __tablename__ = "low_buy_pool_snapshots"
    __table_args__ = (
        UniqueConstraint("latest_trade_date", "symbol", name="uq_low_buy_pool_snapshot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    latest_trade_date: Mapped[str] = mapped_column(String(16), index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    board_date: Mapped[str] = mapped_column(String(16), index=True)
    board_count: Mapped[int] = mapped_column(Integer, default=1)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    industry: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

class LowBuyStrategyPoolSnapshot(Base):
    __tablename__ = "low_buy_strategy_pool_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "latest_trade_date",
            "pool_key",
            "strategy_key",
            "symbol",
            name="uq_low_buy_strategy_pool_snapshot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    latest_trade_date: Mapped[str] = mapped_column(String(16), index=True)
    pool_key: Mapped[str] = mapped_column(String(80), index=True)
    strategy_key: Mapped[str] = mapped_column(String(80), index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    industry: Mapped[str] = mapped_column(String(64), default="")
    anchor_date: Mapped[str] = mapped_column(String(16), index=True)
    anchor_type: Mapped[str] = mapped_column(String(32), default="")
    rank_score: Mapped[float] = mapped_column(Float, default=0.0)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    board_count: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str] = mapped_column(String(48), default="strategy_pool")
    pool_version: Mapped[str] = mapped_column(String(32), default="v1")
    features_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

class LowBuyHotIndustrySnapshot(Base):
    __tablename__ = "low_buy_hot_industry_snapshots"
    __table_args__ = (
        UniqueConstraint("latest_trade_date", name="uq_low_buy_hot_industry_snapshot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    latest_trade_date: Mapped[str] = mapped_column(String(16), index=True)
    source: Mapped[str] = mapped_column(String(32), default="unavailable")
    industries_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

class LowBuyScanSnapshot(Base):
    __tablename__ = "low_buy_scan_snapshots"
    __table_args__ = (
        UniqueConstraint("latest_trade_date", "strategy_key", name="uq_low_buy_scan_snapshot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    latest_trade_date: Mapped[str] = mapped_column(String(16), index=True)
    strategy_key: Mapped[str] = mapped_column(String(80), index=True)
    strategy_title: Mapped[str] = mapped_column(String(64), default="")
    strategy_subtitle: Mapped[str] = mapped_column(String(120), default="")
    strategy_logic: Mapped[str] = mapped_column(Text, default="")
    as_of_date: Mapped[str] = mapped_column(String(32), default="")
    pool_size: Mapped[int] = mapped_column(Integer, default=0)
    scanned_count: Mapped[int] = mapped_column(Integer, default=0)
    matched_count: Mapped[int] = mapped_column(Integer, default=0)
    requested_scan_limit: Mapped[int] = mapped_column(Integer, default=0)
    active_scan_limit: Mapped[int] = mapped_column(Integer, default=0)
    retracement_distribution_json: Mapped[str] = mapped_column(Text, default="{}")
    filters_json: Mapped[str] = mapped_column(Text, default="{}")
    strategy_notes_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

class LowBuyResultSnapshot(Base):
    __tablename__ = "low_buy_result_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "latest_trade_date",
            "strategy_key",
            "symbol",
            name="uq_low_buy_result_snapshot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    latest_trade_date: Mapped[str] = mapped_column(String(16), index=True)
    strategy_key: Mapped[str] = mapped_column(String(80), index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    buy_signal_state: Mapped[str] = mapped_column(String(32), default="watch", index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class StrategyTrackingSnapshot(Base):
    __tablename__ = "strategy_tracking_snapshots"
    __table_args__ = (
        UniqueConstraint("snapshot_key", name="uq_strategy_tracking_snapshot_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_key: Mapped[str] = mapped_column(String(180), index=True)
    as_of_date: Mapped[str] = mapped_column(String(16), default="", index=True)
    range_days: Mapped[int] = mapped_column(Integer, default=30, index=True)
    strategy_key: Mapped[str] = mapped_column(String(80), default="", index=True)
    strategy_family: Mapped[str] = mapped_column(String(40), default="", index=True)
    market_scope: Mapped[str] = mapped_column(String(80), default="all", index=True)
    filter_hash: Mapped[str] = mapped_column(String(80), default="")
    data_version: Mapped[str] = mapped_column(String(160), default="", index=True)
    status: Mapped[str] = mapped_column(String(24), default="fresh", index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    source_data_cutoff: Mapped[str] = mapped_column(String(40), default="")
    payload_json: Mapped[str] = mapped_column(LONGTEXT().with_variant(Text(), "sqlite"), default="{}")
    metrics_json: Mapped[str] = mapped_column(LONGTEXT().with_variant(Text(), "sqlite"), default="{}")
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class LowBuyStrategyPerformanceSnapshot(Base):
    __tablename__ = "low_buy_strategy_performance_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "latest_trade_date",
            "strategy_key",
            name="uq_low_buy_strategy_performance_snapshot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    latest_trade_date: Mapped[str] = mapped_column(String(16), index=True)
    strategy_key: Mapped[str] = mapped_column(String(80), index=True)
    lookback_days: Mapped[int] = mapped_column(Integer, default=0)
    signal_count: Mapped[int] = mapped_column(Integer, default=0)
    evaluated_signals: Mapped[int] = mapped_column(Integer, default=0)
    pending_signals: Mapped[int] = mapped_column(Integer, default=0)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    hit_rate: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate_1d: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate_2d: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate_3d: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate_4d: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate_5d: Mapped[float] = mapped_column(Float, default=0.0)
    avg_return_1d: Mapped[float] = mapped_column(Float, default=0.0)
    avg_return_2d: Mapped[float] = mapped_column(Float, default=0.0)
    avg_return_3d: Mapped[float] = mapped_column(Float, default=0.0)
    avg_return_4d: Mapped[float] = mapped_column(Float, default=0.0)
    avg_return_5d: Mapped[float] = mapped_column(Float, default=0.0)
    avg_max_gain_5d: Mapped[float] = mapped_column(Float, default=0.0)
    avg_max_drawdown_5d: Mapped[float] = mapped_column(Float, default=0.0)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

class LowBuyStrategyPerformanceWindowSnapshot(Base):
    __tablename__ = "low_buy_strategy_performance_window_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "latest_trade_date",
            "strategy_key",
            "lookback_days",
            name="uq_low_buy_strategy_performance_window_snapshot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    latest_trade_date: Mapped[str] = mapped_column(String(16), index=True)
    strategy_key: Mapped[str] = mapped_column(String(80), index=True)
    lookback_days: Mapped[int] = mapped_column(Integer, default=0, index=True)
    signal_count: Mapped[int] = mapped_column(Integer, default=0)
    evaluated_signals: Mapped[int] = mapped_column(Integer, default=0)
    pending_signals: Mapped[int] = mapped_column(Integer, default=0)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    hit_rate: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate_1d: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate_2d: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate_3d: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate_4d: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate_5d: Mapped[float] = mapped_column(Float, default=0.0)
    avg_return_1d: Mapped[float] = mapped_column(Float, default=0.0)
    avg_return_2d: Mapped[float] = mapped_column(Float, default=0.0)
    avg_return_3d: Mapped[float] = mapped_column(Float, default=0.0)
    avg_return_4d: Mapped[float] = mapped_column(Float, default=0.0)
    avg_return_5d: Mapped[float] = mapped_column(Float, default=0.0)
    avg_max_gain_5d: Mapped[float] = mapped_column(Float, default=0.0)
    avg_max_drawdown_5d: Mapped[float] = mapped_column(Float, default=0.0)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

class LowBuyCloseReviewSnapshot(Base):
    __tablename__ = "low_buy_close_review_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "latest_trade_date",
            "strategy_key",
            "symbol",
            name="uq_low_buy_close_review_snapshot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    latest_trade_date: Mapped[str] = mapped_column(String(16), index=True)
    strategy_key: Mapped[str] = mapped_column(String(80), index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    signal_state: Mapped[str] = mapped_column(String(16), default="watch", index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

class LowBuyTradeLifecycleSnapshot(Base):
    __tablename__ = "low_buy_trade_lifecycle_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "user_scope",
            "signal_trade_date",
            "strategy_key",
            "symbol",
            name="uq_low_buy_trade_lifecycle_snapshot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_scope: Mapped[str] = mapped_column(String(64), default="default", index=True)
    signal_trade_date: Mapped[str] = mapped_column(String(16), index=True)
    strategy_key: Mapped[str] = mapped_column(String(80), index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    signal_state: Mapped[str] = mapped_column(String(16), default="watch", index=True)
    status: Mapped[str] = mapped_column(String(16), default="planned", index=True)
    entry_plan_low: Mapped[float] = mapped_column(Float, default=0.0)
    entry_plan_high: Mapped[float] = mapped_column(Float, default=0.0)
    stop_loss: Mapped[float] = mapped_column(Float, default=0.0)
    take_profit: Mapped[float] = mapped_column(Float, default=0.0)
    max_holding_days: Mapped[int] = mapped_column(Integer, default=5)
    entry_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    entry_trade_date: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exit_trade_date: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    exit_reason: Mapped[str] = mapped_column(String(80), default="")
    realized_return_pct: Mapped[float] = mapped_column(Float, default=0.0)
    max_gain_pct: Mapped[float] = mapped_column(Float, default=0.0)
    max_drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)
    attribution_note: Mapped[str] = mapped_column(Text, default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
