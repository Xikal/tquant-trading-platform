from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    market: Mapped[str] = mapped_column(String(16), default="CN")
    instrument_type: Mapped[str] = mapped_column(String(16), default="stock", index=True)
    sector_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class InstrumentRule(Base):
    __tablename__ = "instrument_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    turnaround_mode: Mapped[str] = mapped_column(String(8), default="t1")
    supports_positive_t: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_negative_t: Mapped[bool] = mapped_column(Boolean, default=True)
    same_day_sell_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_base_position: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Watchlist(Base):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    base_position: Mapped[int] = mapped_column(Integer, default=1000)
    available_position: Mapped[int] = mapped_column(Integer, default=1000)
    cost_basis: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    memo: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(64), default="")
    password_hash: Mapped[str] = mapped_column(String(220))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    can_paper_trade: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    roles: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    device_name: Mapped[str] = mapped_column(String(80), default="")
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserWatchlist(Base):
    __tablename__ = "user_watchlists"
    __table_args__ = (
        UniqueConstraint("user_id", "symbol", name="uq_user_watchlist_symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    base_position: Mapped[int] = mapped_column(Integer, default=1000)
    available_position: Mapped[int] = mapped_column(Integer, default=1000)
    cost_basis: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    memo: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class WatchlistSignalSnapshot(Base):
    __tablename__ = "watchlist_signal_snapshots"
    __table_args__ = (
        UniqueConstraint("symbol", name="uq_watchlist_signal_snapshot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AnalysisLog(Base):
    __tablename__ = "analysis_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    action: Mapped[str] = mapped_column(String(32), default="hold")
    signal_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_level: Mapped[str] = mapped_column(String(16), default="medium")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SignalReplay(Base):
    __tablename__ = "signal_replays"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_log_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    outcome: Mapped[str] = mapped_column(String(32), default="pending")
    pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    max_favorable_excursion: Mapped[float] = mapped_column(Float, default=0.0)
    max_adverse_excursion: Mapped[float] = mapped_column(Float, default=0.0)
    review_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), default="")
    params_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MarketEventCache(Base):
    __tablename__ = "market_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(String(120))
    risk_level: Mapped[str] = mapped_column(String(16), default="medium")
    description: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(32), default="system")
    event_time: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MinuteBarSnapshot(Base):
    __tablename__ = "minute_bar_snapshots"
    __table_args__ = (
        UniqueConstraint("symbol", "bar_period", "bar_timestamp", name="uq_minute_bar_snapshot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    market: Mapped[str] = mapped_column(String(16), default="CN")
    instrument_type: Mapped[str] = mapped_column(String(16), default="stock", index=True)
    bar_period: Mapped[str] = mapped_column(String(8), default="1m", index=True)
    bar_timestamp: Mapped[str] = mapped_column(String(32), index=True)
    quote_timestamp: Mapped[str] = mapped_column(String(32), default="")
    last_price: Mapped[float] = mapped_column(Float, default=0.0)
    change_pct: Mapped[float] = mapped_column(Float, default=0.0)
    open_price: Mapped[float] = mapped_column(Float, default=0.0)
    close_price: Mapped[float] = mapped_column(Float, default=0.0)
    high_price: Mapped[float] = mapped_column(Float, default=0.0)
    low_price: Mapped[float] = mapped_column(Float, default=0.0)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DailyBarSnapshot(Base):
    __tablename__ = "daily_bar_snapshots"
    __table_args__ = (
        UniqueConstraint("symbol", "trade_date", name="uq_daily_bar_snapshot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    market: Mapped[str] = mapped_column(String(16), default="CN")
    instrument_type: Mapped[str] = mapped_column(String(16), default="stock", index=True)
    trade_date: Mapped[str] = mapped_column(String(16), index=True)
    open_price: Mapped[float] = mapped_column(Float, default=0.0)
    close_price: Mapped[float] = mapped_column(Float, default=0.0)
    high_price: Mapped[float] = mapped_column(Float, default=0.0)
    low_price: Mapped[float] = mapped_column(Float, default=0.0)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    pct_chg: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


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
    buy_signal_state: Mapped[str] = mapped_column(String(16), default="watch", index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
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


class PaperAccount(Base):
    __tablename__ = "paper_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100), default="默认模拟账户")
    initial_cash: Mapped[float] = mapped_column(Numeric(18, 2), default=100000.0)
    cash_available: Mapped[float] = mapped_column(Numeric(18, 2), default=100000.0)
    frozen_cash: Mapped[float] = mapped_column(Numeric(18, 2), default=0.0)
    market_value: Mapped[float] = mapped_column(Numeric(18, 2), default=0.0)
    total_assets: Mapped[float] = mapped_column(Numeric(18, 2), default=100000.0)
    realized_pnl: Mapped[float] = mapped_column(Numeric(18, 2), default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Numeric(18, 2), default=0.0)
    max_drawdown_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0)
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
    cost_basis: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0)
    latest_price: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)
    market_value: Mapped[float] = mapped_column(Numeric(18, 2), default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Numeric(18, 2), default=0.0)
    unrealized_pnl_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0)
    strategy_sources: Mapped[str] = mapped_column(Text, default="[]")
    opened_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
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
    cost_price: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0)
    source_order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("paper_orders.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PaperOrder(Base):
    __tablename__ = "paper_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    side: Mapped[str] = mapped_column(String(10), index=True)
    order_type: Mapped[str] = mapped_column(String(10), default="market")
    price: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer)
    filled_quantity: Mapped[int] = mapped_column(Integer, default=0)
    avg_fill_price: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)
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
    price: Mapped[float] = mapped_column(Numeric(18, 4))
    quantity: Mapped[int] = mapped_column(Integer)
    gross_amount: Mapped[float] = mapped_column(Numeric(18, 2))
    commission: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0)
    stamp_tax: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0)
    transfer_fee: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0)
    net_amount: Mapped[float] = mapped_column(Numeric(18, 2))
    strategy_key: Mapped[str] = mapped_column(String(80), default="")
    market_state: Mapped[str] = mapped_column(String(32), default="")
    trade_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class PaperPerformanceSnapshot(Base):
    __tablename__ = "paper_performance_snapshots"
    __table_args__ = (
        UniqueConstraint("account_id", "snapshot_date", name="uq_paper_perf_account_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    total_assets: Mapped[float] = mapped_column(Numeric(18, 2), default=0.0)
    daily_return_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0)
    cumulative_return_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0)
    max_drawdown_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0)
    win_rate_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0)
    net_win_rate_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0)
    profit_factor: Mapped[Optional[float]] = mapped_column(Numeric(8, 4), nullable=True)
    stop_loss_rate_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0)
    trade_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PaperAgentRun(Base):
    __tablename__ = "paper_agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), index=True)
    provider: Mapped[str] = mapped_column(String(40), default="none", index=True)
    run_type: Mapped[str] = mapped_column(String(40), default="explain", index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    request_json: Mapped[str] = mapped_column(Text, default="{}")
    response_json: Mapped[str] = mapped_column(Text, default="{}")
    error_message: Mapped[str] = mapped_column(String(240), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class IntradayConfirmationSnapshot(Base):
    __tablename__ = "intraday_confirmation_snapshots"
    __table_args__ = (
        UniqueConstraint("symbol", "trade_date", "bar_period", name="uq_intraday_confirmation_symbol_date_period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    trade_date: Mapped[str] = mapped_column(String(16), index=True)
    bar_period: Mapped[str] = mapped_column(String(8), default="1m")
    vwap: Mapped[float] = mapped_column(Float, default=0.0)
    latest_price: Mapped[float] = mapped_column(Float, default=0.0)
    above_vwap: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    late_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(String(240), default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class RiskEvent(Base):
    __tablename__ = "risk_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("paper_accounts.id"), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(16), default="", index=True)
    event_type: Mapped[str] = mapped_column(String(40), default="risk_circuit", index=True)
    severity: Mapped[str] = mapped_column(String(16), default="medium", index=True)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    message: Mapped[str] = mapped_column(String(240), default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    triggered_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class SseSubscription(Base):
    __tablename__ = "sse_subscriptions"
    __table_args__ = (
        UniqueConstraint("client_id", "channel", name="uq_sse_subscription_client_channel"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    client_id: Mapped[str] = mapped_column(String(80), index=True)
    channel: Mapped[str] = mapped_column(String(40), default="intraday", index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    last_event_id: Mapped[str] = mapped_column(String(80), default="")
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
