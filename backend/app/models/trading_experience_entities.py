from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TradingExperienceReviewPoolItem(Base):
    __tablename__ = "trading_experience_review_pool_items"
    __table_args__ = (
        UniqueConstraint("pool_date", "symbol", name="uq_trading_experience_review_pool_day_symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pool_date: Mapped[date] = mapped_column(Date, index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(24), default="in_pool", index=True)
    entry_pct: Mapped[float] = mapped_column(Float, default=0.0)
    volume_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    mainline_state: Mapped[str] = mapped_column(String(48), default="unknown")
    sector_role: Mapped[str] = mapped_column(String(48), default="unknown")
    drop_reason: Mapped[str] = mapped_column(String(120), default="")
    tracked_days: Mapped[int] = mapped_column(Integer, default=0)
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    data_quality: Mapped[str] = mapped_column(String(24), default="insufficient", index=True)
    as_of: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    engine_version: Mapped[str] = mapped_column(String(40), default="trading-experience-v1", index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class TradingExperienceTradeJournalEntry(Base):
    __tablename__ = "trading_experience_trade_journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("paper_accounts.id"), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    action: Mapped[str] = mapped_column(String(16), index=True)
    reason_text: Mapped[str] = mapped_column(Text, default="")
    signal_source: Mapped[str] = mapped_column(String(80), default="")
    discipline_flags_json: Mapped[str] = mapped_column(Text, default="{}")
    mistake_tags_json: Mapped[str] = mapped_column(Text, default="[]")
    data_quality: Mapped[str] = mapped_column(String(24), default="ok", index=True)
    engine_version: Mapped[str] = mapped_column(String(40), default="trading-experience-v1", index=True)
    source: Mapped[str] = mapped_column(String(40), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class TradingExperienceSnapshot(Base):
    __tablename__ = "trading_experience_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_type",
            "snapshot_key",
            "trade_date",
            "engine_version",
            name="uq_trading_experience_snapshot_type_key_day_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_type: Mapped[str] = mapped_column(String(64), index=True)
    snapshot_key: Mapped[str] = mapped_column(String(120), index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    data_quality: Mapped[str] = mapped_column(String(24), default="insufficient", index=True)
    as_of: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    engine_version: Mapped[str] = mapped_column(String(40), default="trading-experience-v1", index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
