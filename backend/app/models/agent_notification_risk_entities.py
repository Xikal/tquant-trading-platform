from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


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

class AgentAuditLog(Base):
    """Durable audit trail for Agent tool invocations."""

    __tablename__ = "agent_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(80), index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    provider_name: Mapped[str] = mapped_column(String(40), default="none", index=True)
    tool_name: Mapped[str] = mapped_column(String(80), index=True)
    permission: Mapped[str] = mapped_column(String(20), default="read", index=True)
    input_arguments: Mapped[str] = mapped_column(Text, default="{}")
    result_summary: Mapped[str] = mapped_column(Text, default="{}")
    ok: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str] = mapped_column(String(60), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

class NotificationEvent(Base):
    """Notification de-duplication and signal-upgrade ledger.

    One row tracks one logical notification target, e.g. user + channel +
    stock + strategy.  The row is updated when the same signal is seen again,
    or when it upgrades to a stronger state.
    """

    __tablename__ = "notification_events"
    __table_args__ = (
        UniqueConstraint(
            "scope_key",
            "channel",
            "event_type",
            "symbol",
            "strategy_key",
            name="uq_notification_event_target",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope_key: Mapped[str] = mapped_column(String(80), default="global", index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(32), default="feishu", index=True)
    event_type: Mapped[str] = mapped_column(String(40), default="signal", index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    strategy_key: Mapped[str] = mapped_column(String(80), default="", index=True)
    strategy_title: Mapped[str] = mapped_column(String(80), default="")
    signal_state: Mapped[str] = mapped_column(String(32), default="", index=True)
    signal_rank: Mapped[int] = mapped_column(Integer, default=0)
    previous_signal_state: Mapped[str] = mapped_column(String(32), default="")
    upgraded: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    notification_count: Mapped[int] = mapped_column(Integer, default=0)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    last_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
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
