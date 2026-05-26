"""add market pulse and hourly snapshot history

Revision ID: 20260526_0001
Revises: 20260525_0001
Create Date: 2026-05-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260526_0001"
down_revision = "20260525_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "market_hourly_snapshot_history" not in tables:
        op.create_table(
            "market_hourly_snapshot_history",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("trade_date", sa.String(length=16), nullable=False),
            sa.Column("snapshot_bucket", sa.String(length=24), nullable=False),
            sa.Column("data_quality", sa.String(length=24), nullable=False),
            sa.Column("snapshot_count", sa.Integer(), nullable=False),
            sa.Column("market_strength_score", sa.Float(), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint("trade_date", "snapshot_bucket", name="uq_market_hourly_snapshot_bucket"),
        )
        op.create_index("ix_market_hourly_snapshot_history_trade_date", "market_hourly_snapshot_history", ["trade_date"])
        op.create_index(
            "ix_market_hourly_snapshot_history_snapshot_bucket",
            "market_hourly_snapshot_history",
            ["snapshot_bucket"],
        )
        op.create_index(
            "ix_market_hourly_snapshot_history_data_quality",
            "market_hourly_snapshot_history",
            ["data_quality"],
        )
        op.create_index("ix_market_hourly_snapshot_history_created_at", "market_hourly_snapshot_history", ["created_at"])
        op.create_index("ix_market_hourly_snapshot_history_updated_at", "market_hourly_snapshot_history", ["updated_at"])

    if "market_pulse_events" not in tables:
        op.create_table(
            "market_pulse_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("trade_date", sa.String(length=16), nullable=False),
            sa.Column("pulse_level", sa.String(length=24), nullable=False),
            sa.Column("data_quality", sa.String(length=24), nullable=False),
            sa.Column("pulse_text", sa.Text(), nullable=False),
            sa.Column("suggested_action", sa.Text(), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index("ix_market_pulse_events_trade_date", "market_pulse_events", ["trade_date"])
        op.create_index("ix_market_pulse_events_pulse_level", "market_pulse_events", ["pulse_level"])
        op.create_index("ix_market_pulse_events_data_quality", "market_pulse_events", ["data_quality"])
        op.create_index("ix_market_pulse_events_created_at", "market_pulse_events", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "market_pulse_events" in tables:
        for index_name in (
            "ix_market_pulse_events_created_at",
            "ix_market_pulse_events_data_quality",
            "ix_market_pulse_events_pulse_level",
            "ix_market_pulse_events_trade_date",
        ):
            if index_name in {index["name"] for index in inspector.get_indexes("market_pulse_events")}:
                op.drop_index(index_name, table_name="market_pulse_events")
        op.drop_table("market_pulse_events")
    if "market_hourly_snapshot_history" in tables:
        for index_name in (
            "ix_market_hourly_snapshot_history_updated_at",
            "ix_market_hourly_snapshot_history_created_at",
            "ix_market_hourly_snapshot_history_data_quality",
            "ix_market_hourly_snapshot_history_snapshot_bucket",
            "ix_market_hourly_snapshot_history_trade_date",
        ):
            if index_name in {index["name"] for index in inspector.get_indexes("market_hourly_snapshot_history")}:
                op.drop_index(index_name, table_name="market_hourly_snapshot_history")
        op.drop_table("market_hourly_snapshot_history")
