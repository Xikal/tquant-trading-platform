from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BacktestDatasetManifest(Base):
    __tablename__ = "backtest_dataset_manifests"
    __table_args__ = (
        UniqueConstraint("dataset_key", "manifest_hash", name="uq_backtest_dataset_manifest"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_key: Mapped[str] = mapped_column(String(80), index=True)
    manifest_hash: Mapped[str] = mapped_column(String(120), index=True)
    data_version: Mapped[str] = mapped_column(String(80), default="")
    start_date: Mapped[str] = mapped_column(String(16), default="", index=True)
    end_date: Mapped[str] = mapped_column(String(16), default="", index=True)
    instrument_count: Mapped[int] = mapped_column(Integer, default=0)
    bar_count: Mapped[int] = mapped_column(Integer, default=0)
    quality_summary_json: Mapped[str] = mapped_column(Text, default="{}")
    source_summary_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BacktestOrder(Base):
    __tablename__ = "backtest_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("backtest_runs.id"), index=True)
    trade_date: Mapped[str] = mapped_column(String(16), index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    side: Mapped[str] = mapped_column(String(12), index=True)
    order_type: Mapped[str] = mapped_column(String(24), default="market")
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    strategy_key: Mapped[str] = mapped_column(String(80), default="", index=True)
    signal_state: Mapped[str] = mapped_column(String(32), default="", index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    filled_quantity: Mapped[int] = mapped_column(Integer, default=0)
    requested_price: Mapped[float] = mapped_column(Float, default=0.0)
    limit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    filled_price: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(String(240), default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("backtest_runs.id"), index=True)
    order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("backtest_orders.id"), nullable=True, index=True)
    trade_date: Mapped[str] = mapped_column(String(16), index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    side: Mapped[str] = mapped_column(String(12), index=True)
    strategy_key: Mapped[str] = mapped_column(String(80), default="", index=True)
    signal_state: Mapped[str] = mapped_column(String(32), default="", index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    gross_amount: Mapped[float] = mapped_column(Float, default=0.0)
    fee_amount: Mapped[float] = mapped_column(Float, default=0.0)
    slippage_amount: Mapped[float] = mapped_column(Float, default=0.0)
    net_amount: Mapped[float] = mapped_column(Float, default=0.0)
    pnl_amount: Mapped[float] = mapped_column(Float, default=0.0)
    pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    holding_days: Mapped[int] = mapped_column(Integer, default=0)
    entry_reason: Mapped[str] = mapped_column(String(80), default="")
    exit_reason: Mapped[str] = mapped_column(String(80), default="")
    market_state: Mapped[str] = mapped_column(String(40), default="", index=True)
    sector_name: Mapped[str] = mapped_column(String(80), default="", index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BacktestDailySnapshot(Base):
    __tablename__ = "backtest_daily_snapshots"
    __table_args__ = (
        UniqueConstraint("run_id", "trade_date", name="uq_backtest_daily_snapshot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("backtest_runs.id"), index=True)
    trade_date: Mapped[str] = mapped_column(String(16), index=True)
    cash: Mapped[float] = mapped_column(Float, default=0.0)
    market_value: Mapped[float] = mapped_column(Float, default=0.0)
    equity: Mapped[float] = mapped_column(Float, default=0.0)
    daily_return_pct: Mapped[float] = mapped_column(Float, default=0.0)
    drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)
    exposure_pct: Mapped[float] = mapped_column(Float, default=0.0)
    positions_count: Mapped[int] = mapped_column(Integer, default=0)
    turnover: Mapped[float] = mapped_column(Float, default=0.0)
    benchmark_symbol: Mapped[str] = mapped_column(String(24), default="")
    benchmark_close: Mapped[float] = mapped_column(Float, default=0.0)
    benchmark_return_pct: Mapped[float] = mapped_column(Float, default=0.0)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BacktestDataQuality(Base):
    __tablename__ = "backtest_data_quality"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("backtest_runs.id"), nullable=True, index=True)
    dataset_manifest_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("backtest_dataset_manifests.id"), nullable=True, index=True
    )
    trade_date: Mapped[str] = mapped_column(String(16), default="", index=True)
    symbol: Mapped[str] = mapped_column(String(16), default="", index=True)
    quality_tag: Mapped[str] = mapped_column(String(24), default="unknown", index=True)
    issue_type: Mapped[str] = mapped_column(String(64), default="", index=True)
    severity: Mapped[str] = mapped_column(String(24), default="info", index=True)
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
