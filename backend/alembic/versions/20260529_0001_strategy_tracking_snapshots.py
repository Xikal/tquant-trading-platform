"""add strategy tracking snapshots

Revision ID: 20260529_0001
Revises: 20260528_0002
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260529_0001"
down_revision = "20260528_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "strategy_tracking_snapshots" in set(inspector.get_table_names()):
        return
    op.create_table(
        "strategy_tracking_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("snapshot_key", sa.String(length=180), nullable=False),
        sa.Column("as_of_date", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("range_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("strategy_key", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("strategy_family", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("market_scope", sa.String(length=80), nullable=False, server_default="all"),
        sa.Column("filter_hash", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("data_version", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="fresh"),
        sa.Column("generated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("source_data_cutoff", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("snapshot_key", name="uq_strategy_tracking_snapshot_key"),
    )
    for index_name, columns in (
        ("ix_strategy_tracking_snapshots_snapshot_key", ["snapshot_key"]),
        ("ix_strategy_tracking_snapshots_as_of_date", ["as_of_date"]),
        ("ix_strategy_tracking_snapshots_range_days", ["range_days"]),
        ("ix_strategy_tracking_snapshots_strategy_key", ["strategy_key"]),
        ("ix_strategy_tracking_snapshots_strategy_family", ["strategy_family"]),
        ("ix_strategy_tracking_snapshots_market_scope", ["market_scope"]),
        ("ix_strategy_tracking_snapshots_data_version", ["data_version"]),
        ("ix_strategy_tracking_snapshots_status", ["status"]),
        ("ix_strategy_tracking_snapshots_generated_at", ["generated_at"]),
    ):
        op.create_index(index_name, "strategy_tracking_snapshots", columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "strategy_tracking_snapshots" not in set(inspector.get_table_names()):
        return
    existing_indexes = {index["name"] for index in inspector.get_indexes("strategy_tracking_snapshots")}
    for index_name in (
        "ix_strategy_tracking_snapshots_generated_at",
        "ix_strategy_tracking_snapshots_status",
        "ix_strategy_tracking_snapshots_data_version",
        "ix_strategy_tracking_snapshots_market_scope",
        "ix_strategy_tracking_snapshots_strategy_family",
        "ix_strategy_tracking_snapshots_strategy_key",
        "ix_strategy_tracking_snapshots_range_days",
        "ix_strategy_tracking_snapshots_as_of_date",
        "ix_strategy_tracking_snapshots_snapshot_key",
    ):
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name="strategy_tracking_snapshots")
    op.drop_table("strategy_tracking_snapshots")

