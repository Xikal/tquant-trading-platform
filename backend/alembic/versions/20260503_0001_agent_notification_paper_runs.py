"""agent notification and paper automation tables

Revision ID: 20260503_0001
Revises:
Create Date: 2026-05-03
"""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20260503_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "paper_agent_runs" not in tables:
        op.create_table(
            "paper_agent_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("account_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=40), nullable=False, server_default="none"),
            sa.Column("run_type", sa.String(length=40), nullable=False, server_default="explain"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("request_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("response_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("error_message", sa.String(length=240), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["account_id"], ["paper_accounts.id"]),
        )
    if "agent_audit_log" not in tables:
        op.create_table(
            "agent_audit_log",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("trace_id", sa.String(length=80), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("provider_name", sa.String(length=40), nullable=False, server_default="none"),
            sa.Column("tool_name", sa.String(length=80), nullable=False),
            sa.Column("permission", sa.String(length=20), nullable=False, server_default="read"),
            sa.Column("input_arguments", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("result_summary", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("ok", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_code", sa.String(length=60), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        )
    if "notification_events" not in tables:
        op.create_table(
            "notification_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("scope_key", sa.String(length=80), nullable=False, server_default="global"),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("channel", sa.String(length=32), nullable=False, server_default="feishu"),
            sa.Column("event_type", sa.String(length=40), nullable=False, server_default="signal"),
            sa.Column("symbol", sa.String(length=16), nullable=False),
            sa.Column("name", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("strategy_key", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("strategy_title", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("signal_state", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("signal_rank", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("previous_signal_state", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("upgraded", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("notification_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("last_notified_at", sa.DateTime(), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.UniqueConstraint("scope_key", "channel", "event_type", "symbol", "strategy_key", name="uq_notification_event_target"),
        )
    _ensure_indexes(
        inspector=sa.inspect(bind),
        specs=(
            ("paper_agent_runs", "ix_paper_agent_runs_account_created", ("account_id", "created_at")),
            ("paper_agent_runs", "ix_paper_agent_runs_status", ("status",)),
            ("agent_audit_log", "ix_agent_audit_tool_created", ("tool_name", "created_at")),
            ("agent_audit_log", "ix_agent_audit_provider_created", ("provider_name", "created_at")),
            ("notification_events", "ix_notify_scope_channel_seen", ("scope_key", "channel", "last_seen_at")),
            ("notification_events", "ix_notify_symbol_strategy_state", ("symbol", "strategy_key", "signal_state")),
        ),
    )


def downgrade() -> None:
    # Keep operational telemetry tables by default. Dropping audit and
    # notification ledgers during downgrade would remove user-visible history.
    pass


def _ensure_indexes(*, inspector, specs: Sequence[tuple[str, str, tuple[str, ...]]]) -> None:
    tables = set(inspector.get_table_names())
    for table_name, index_name, columns in specs:
        if table_name not in tables:
            continue
        existing = {item["name"] for item in inspector.get_indexes(table_name)}
        if index_name not in existing:
            op.create_index(index_name, table_name, list(columns))
