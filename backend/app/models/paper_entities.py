from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PaperAccount(Base):
    __tablename__ = "paper_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100), default="默认模拟账户")
    initial_cash: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("100000.00"))
    cash_available: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("100000.00"))
    frozen_cash: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"))
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"))
    total_assets: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("100000.00"))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"))
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"))
    max_drawdown_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.0000"))
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

class PaperPosition(Base):
    __tablename__ = "paper_positions"
    __table_args__ = (
        UniqueConstraint("account_id", "symbol", name="uq_paper_position_account_symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    available_quantity: Mapped[int] = mapped_column(Integer, default=0)
    frozen_quantity: Mapped[int] = mapped_column(Integer, default=0)
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0000"))
    latest_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"))
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"))
    unrealized_pnl_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.0000"))
    strategy_sources: Mapped[str] = mapped_column(Text, default="[]")
    opened_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    lots: Mapped[list["PaperPositionLot"]] = relationship(
        "PaperPositionLot",
        back_populates="position",
        lazy="selectin",
    )

class PaperPositionLot(Base):
    __tablename__ = "paper_position_lots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), index=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("paper_positions.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    remaining: Mapped[int] = mapped_column(Integer)
    available_date: Mapped[date] = mapped_column(Date, index=True)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0000"))
    source_order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("paper_orders.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    position: Mapped[PaperPosition] = relationship("PaperPosition", back_populates="lots")

class PaperOrder(Base):
    __tablename__ = "paper_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    side: Mapped[str] = mapped_column(String(10), index=True)
    order_type: Mapped[str] = mapped_column(String(10), default="market")
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer)
    filled_quantity: Mapped[int] = mapped_column(Integer, default=0)
    avg_fill_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    reject_reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="manual", index=True)
    strategy_key: Mapped[str] = mapped_column(String(80), default="")
    signal_snapshot: Mapped[str] = mapped_column(Text, default="{}")
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("paper_orders.id"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    side: Mapped[str] = mapped_column(String(10), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    quantity: Mapped[int] = mapped_column(Integer)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    commission: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0000"))
    stamp_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0000"))
    transfer_fee: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0000"))
    net_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    strategy_key: Mapped[str] = mapped_column(String(80), default="")
    market_state: Mapped[str] = mapped_column(String(32), default="")
    entry_reason: Mapped[str] = mapped_column(String(240), default="")
    exit_reason: Mapped[str] = mapped_column(String(80), default="")
    trade_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

class PaperTradeTag(Base):
    __tablename__ = "paper_trade_tags"
    __table_args__ = (
        UniqueConstraint("trade_id", "tag", name="uq_paper_trade_tag"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_id: Mapped[int] = mapped_column(ForeignKey("paper_trades.id"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    tag: Mapped[str] = mapped_column(String(40), index=True)
    note: Mapped[str] = mapped_column(String(240), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

class PaperPerformanceSnapshot(Base):
    __tablename__ = "paper_performance_snapshots"
    __table_args__ = (
        UniqueConstraint("account_id", "snapshot_date", name="uq_paper_perf_account_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    total_assets: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"))
    daily_return_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.0000"))
    cumulative_return_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.0000"))
    max_drawdown_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.0000"))
    win_rate_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.0000"))
    net_win_rate_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.0000"))
    profit_factor: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    stop_loss_rate_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.0000"))
    trade_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class PaperStrategyPerfDaily(Base):
    """策略级每日绩效快照，用于模拟盘趋势分析。"""

    __tablename__ = "paper_strategy_perf_daily"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "snapshot_date",
            "strategy_key",
            name="uq_pspd_account_date_strategy",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    strategy_key: Mapped[str] = mapped_column(String(80), index=True)
    trade_count: Mapped[int] = mapped_column(Integer, default=0)
    win_count: Mapped[int] = mapped_column(Integer, default=0)
    loss_count: Mapped[int] = mapped_column(Integer, default=0)
    win_rate_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0)
    net_win_rate_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0)
    avg_return_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0)
    total_pnl: Mapped[float] = mapped_column(Numeric(18, 2), default=0.0)
    profit_factor: Mapped[Optional[float]] = mapped_column(Numeric(8, 4), nullable=True)
    avg_hold_hours: Mapped[float] = mapped_column(Numeric(8, 2), default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class PaperMarketPerfDaily(Base):
    """市场状态级每日绩效快照，用于评估不同环境下的模拟盘表现。"""

    __tablename__ = "paper_market_perf_daily"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "snapshot_date",
            "market_state",
            name="uq_pmpd_account_date_market",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    market_state: Mapped[str] = mapped_column(String(32), index=True)
    trade_count: Mapped[int] = mapped_column(Integer, default=0)
    win_rate_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0)
    net_win_rate_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0)
    avg_return_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0)
    profit_factor: Mapped[Optional[float]] = mapped_column(Numeric(8, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class _PaperReportFields:
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), index=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    overall_summary: Mapped[str] = mapped_column(Text, default="")
    strategy_highlights: Mapped[str] = mapped_column(Text, default="[]")
    risk_alerts: Mapped[str] = mapped_column(Text, default="[]")
    suggestion: Mapped[str] = mapped_column(Text, default="")
    raw_metrics_snapshot: Mapped[str] = mapped_column(Text, default="{}")
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    llm_model: Mapped[str] = mapped_column(String(80), default="")


class PaperDailyReport(_PaperReportFields, Base):
    """模拟盘每日战绩点评，存储规则或大模型生成的复盘摘要。"""

    __tablename__ = "paper_daily_reports"
    __table_args__ = (
        UniqueConstraint("account_id", "report_date", name="uq_pdr_account_date"),
    )


class PaperReviewReport(_PaperReportFields, Base):
    """午盘/收盘两段式复盘，用于盘中指导与收盘总结。"""

    __tablename__ = "paper_review_reports"
    __table_args__ = (
        UniqueConstraint("account_id", "report_date", "report_slot", name="uq_prr_account_date_slot"),
    )

    report_slot: Mapped[str] = mapped_column(String(16), default="close", index=True)
