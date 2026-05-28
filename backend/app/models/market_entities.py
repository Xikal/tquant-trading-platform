from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.sqlalchemy_types import FlexibleDate


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    market: Mapped[str] = mapped_column(String(16), default="CN")
    instrument_type: Mapped[str] = mapped_column(String(16), default="stock", index=True)
    sector_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    listing_date: Mapped[Optional[date]] = mapped_column(FlexibleDate(), nullable=True, index=True)
    delisting_date: Mapped[Optional[date]] = mapped_column(FlexibleDate(), nullable=True, index=True)
    is_st: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class InstrumentIndustryHistory(Base):
    __tablename__ = "instrument_industry_history"
    __table_args__ = (
        UniqueConstraint("symbol", "trade_date", "industry_name", name="uq_instrument_industry_history_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    trade_date: Mapped[date] = mapped_column(FlexibleDate(), index=True)
    industry_name: Mapped[str] = mapped_column(String(80), default="", index=True)
    source: Mapped[str] = mapped_column(String(48), default="unknown", index=True)
    data_quality: Mapped[str] = mapped_column(String(24), default="unknown", index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class InstrumentConceptHistory(Base):
    __tablename__ = "instrument_concept_history"
    __table_args__ = (
        UniqueConstraint("symbol", "trade_date", "concept_name", name="uq_instrument_concept_history_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    trade_date: Mapped[date] = mapped_column(FlexibleDate(), index=True)
    concept_name: Mapped[str] = mapped_column(String(80), default="", index=True)
    source: Mapped[str] = mapped_column(String(48), default="unknown", index=True)
    data_quality: Mapped[str] = mapped_column(String(24), default="unknown", index=True)
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


class StrategyMetadata(Base):
    __tablename__ = "strategy_metadata"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(32), default="")
    risk_level: Mapped[str] = mapped_column(String(16), default="medium")
    typical_holding_days: Mapped[str] = mapped_column(String(24), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True, index=True)
    probe_status: Mapped[str] = mapped_column(String(20), default="not_required", nullable=True, index=True)
    probe_summary: Mapped[str] = mapped_column(Text, default="", nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), default="full", nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class StrategyTierOverride(Base):
    __tablename__ = "strategy_tier_overrides"
    __table_args__ = (
        UniqueConstraint("strategy_key", name="uq_strategy_tier_override_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    strategy_key: Mapped[str] = mapped_column(String(80), index=True)
    override_tier: Mapped[str] = mapped_column(String(20), default="research", index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    evidence_summary: Mapped[str] = mapped_column(Text, default="")
    operator_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    promoted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    reverted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class StrategyTierOverrideLog(Base):
    __tablename__ = "strategy_tier_override_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    strategy_key: Mapped[str] = mapped_column(String(80), index=True)
    action: Mapped[str] = mapped_column(String(20), default="", index=True)
    from_tier: Mapped[str] = mapped_column(String(20), default="")
    to_tier: Mapped[str] = mapped_column(String(20), default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    evidence_summary: Mapped[str] = mapped_column(Text, default="")
    operator_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class TradingElasticityCache(Base):
    __tablename__ = "trading_elasticity_cache"
    __table_args__ = (
        UniqueConstraint("symbol", name="uq_trading_elasticity_symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    elasticity_score: Mapped[float] = mapped_column(Float, default=10.0)
    elasticity_tier: Mapped[str] = mapped_column(String(12), default="★★")
    data_quality: Mapped[str] = mapped_column(String(24), default="unavailable", index=True)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class MarketModelObservation(Base):
    __tablename__ = "market_model_observations"
    __table_args__ = (
        UniqueConstraint(
            "model_key",
            "symbol",
            "trade_date",
            "signal_state",
            name="uq_market_model_observation_signal_day",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_key: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(String(16), default="", index=True)
    name: Mapped[str] = mapped_column(String(80), default="")
    trade_date: Mapped[str] = mapped_column(String(16), default="", index=True)
    signal_state: Mapped[str] = mapped_column(String(32), default="", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    expected_edge_pct: Mapped[float] = mapped_column(Float, default=0.0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    outcome_status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    observed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class FeatureFlagAuditLog(Base):
    __tablename__ = "feature_flag_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    flag_key: Mapped[str] = mapped_column(String(64), index=True)
    old_value: Mapped[str] = mapped_column(Text, default="")
    new_value: Mapped[str] = mapped_column(Text, default="")
    operator_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    operator_ip: Mapped[str] = mapped_column(String(80), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class StrategyPreset(Base):
    __tablename__ = "strategy_presets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    preset_key: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class Watchlist(Base):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    base_position: Mapped[int] = mapped_column(Integer, default=1000)
    available_position: Mapped[int] = mapped_column(Integer, default=1000)
    available_position_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    cost_basis: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    memo: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    latest_signal: Mapped[Optional["WatchlistSignalSnapshot"]] = relationship(
        "WatchlistSignalSnapshot",
        uselist=False,
        primaryjoin="Watchlist.symbol == foreign(WatchlistSignalSnapshot.symbol)",
        viewonly=True,
        lazy="selectin",
    )

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
    available_position_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
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
    watchlist: Mapped[Optional[Watchlist]] = relationship(
        "Watchlist",
        uselist=False,
        primaryjoin="foreign(WatchlistSignalSnapshot.symbol) == Watchlist.symbol",
        viewonly=True,
        lazy="selectin",
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
    owner_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="succeeded", index=True)
    strategy_keys: Mapped[str] = mapped_column(String(300), default="", index=True)
    start_date: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, index=True)
    end_date: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, index=True)
    benchmark_symbol: Mapped[str] = mapped_column(String(24), default="")
    initial_cash: Mapped[float] = mapped_column(Float, default=0.0)
    final_equity: Mapped[float] = mapped_column(Float, default=0.0)
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0)
    max_duration_seconds: Mapped[int] = mapped_column(Integer, default=1800)
    optimization_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    validation_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    dataset_manifest_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    engine_version: Mapped[str] = mapped_column(String(48), default="backtest-v2")
    strategy_version: Mapped[str] = mapped_column(String(80), default="")
    data_version: Mapped[str] = mapped_column(String(80), default="")
    fee_model_version: Mapped[str] = mapped_column(String(80), default="")
    slippage_bps: Mapped[float] = mapped_column(Float, default=0.0)
    error_message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

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
    trade_date: Mapped[Optional[date]] = mapped_column(FlexibleDate(), nullable=True, index=True)
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
    bid_ask_spread: Mapped[float] = mapped_column(Float, default=0.0)
    premium_discount_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tracking_index_symbol: Mapped[str] = mapped_column(String(32), default="", index=True)
    liquidity_tier: Mapped[str] = mapped_column(String(24), default="unknown", index=True)
    source: Mapped[str] = mapped_column(String(48), default="unknown", index=True)
    fetch_time: Mapped[str] = mapped_column(String(32), default="", index=True)
    checksum: Mapped[str] = mapped_column(String(64), default="", index=True)
    data_quality: Mapped[str] = mapped_column(String(24), default="unknown", index=True)
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
    trade_date: Mapped[date] = mapped_column(FlexibleDate(), index=True)
    open_price: Mapped[float] = mapped_column(Numeric(18, 4, asdecimal=False), default=0.0)
    close_price: Mapped[float] = mapped_column(Numeric(18, 4, asdecimal=False), default=0.0)
    high_price: Mapped[float] = mapped_column(Numeric(18, 4, asdecimal=False), default=0.0)
    low_price: Mapped[float] = mapped_column(Numeric(18, 4, asdecimal=False), default=0.0)
    volume: Mapped[float] = mapped_column(Numeric(20, 0, asdecimal=False), default=0.0)
    amount: Mapped[float] = mapped_column(Numeric(20, 2, asdecimal=False), default=0.0)
    pct_chg: Mapped[float] = mapped_column(Float, default=0.0)
    pre_close: Mapped[float] = mapped_column(Float, default=0.0)
    limit_up_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=True)
    limit_down_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=True)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_st: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_delisted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    source: Mapped[str] = mapped_column(String(48), default="unknown", index=True)
    fetch_time: Mapped[str] = mapped_column(String(32), default="", index=True)
    adjusted_mode: Mapped[str] = mapped_column(String(16), default="unknown", index=True)
    checksum: Mapped[str] = mapped_column(String(64), default="", index=True)
    data_quality: Mapped[str] = mapped_column(String(24), default="unknown", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

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


class MarketRegimeSnapshotCache(Base):
    __tablename__ = "market_regime_snapshots"
    __table_args__ = (
        UniqueConstraint("cache_key", name="uq_market_regime_snapshot_cache_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(120), index=True)
    trade_date: Mapped[str] = mapped_column(String(16), index=True)
    state: Mapped[str] = mapped_column(String(40), default="", index=True)
    breadth_ready: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    emotion_ready: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    hot_industry_source: Mapped[str] = mapped_column(String(40), default="", index=True)
    data_quality: Mapped[str] = mapped_column(String(24), default="limited", index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), index=True
    )


class MarketHourlySnapshotHistory(Base):
    __tablename__ = "market_hourly_snapshot_history"
    __table_args__ = (
        UniqueConstraint("trade_date", "snapshot_bucket", name="uq_market_hourly_snapshot_bucket"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_date: Mapped[str] = mapped_column(String(16), index=True)
    snapshot_bucket: Mapped[str] = mapped_column(String(24), index=True)
    data_quality: Mapped[str] = mapped_column(String(24), default="fresh", index=True)
    snapshot_count: Mapped[int] = mapped_column(Integer, default=0)
    market_strength_score: Mapped[float] = mapped_column(Float, default=0.0)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), index=True
    )


class MarketPulseEvent(Base):
    __tablename__ = "market_pulse_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_date: Mapped[str] = mapped_column(String(16), index=True)
    pulse_level: Mapped[str] = mapped_column(String(24), default="unknown", index=True)
    data_quality: Mapped[str] = mapped_column(String(24), default="unavailable", index=True)
    pulse_text: Mapped[str] = mapped_column(Text, default="")
    suggested_action: Mapped[str] = mapped_column(Text, default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class MarketReviewReport(Base):
    __tablename__ = "market_review_reports"
    __table_args__ = (
        UniqueConstraint("report_date", "report_slot", name="uq_market_review_date_slot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    report_slot: Mapped[str] = mapped_column(String(16), default="close", index=True)
    overall_summary: Mapped[str] = mapped_column(Text, default="")
    strategy_highlights: Mapped[str] = mapped_column(Text, default="[]")
    risk_alerts: Mapped[str] = mapped_column(Text, default="[]")
    suggestion: Mapped[str] = mapped_column(Text, default="")
    raw_metrics_snapshot: Mapped[str] = mapped_column(Text, default="{}")
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    llm_model: Mapped[str] = mapped_column(String(80), default="market-rule")
