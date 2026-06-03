"""add key level snapshots table

Revision ID: 20260603_0001
Revises: 20260602_0001
Create Date: 2026-06-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision = "20260603_0001"
down_revision = "20260602_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "key_level_snapshots" in set(inspector.get_table_names()):
        return
    op.create_table(
        "key_level_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("cache_key", sa.String(length=120), nullable=False),
        sa.Column("symbol", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("trade_date", sa.String(length=16), nullable=False),
        sa.Column("engine_version", sa.String(length=40), nullable=False, server_default="akey-level-v1"),
        sa.Column("data_quality", sa.String(length=24), nullable=False, server_default="insufficient"),
        sa.Column("payload_json", mysql.LONGTEXT().with_variant(sa.Text(), "sqlite"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "scope",
            "cache_key",
            "trade_date",
            "engine_version",
            name="uq_key_level_snapshot_scope_key_day_version",
        ),
    )
    for index_name, columns in (
        ("ix_key_level_snapshots_scope", ["scope"]),
        ("ix_key_level_snapshots_cache_key", ["cache_key"]),
        ("ix_key_level_snapshots_symbol", ["symbol"]),
        ("ix_key_level_snapshots_trade_date", ["trade_date"]),
        ("ix_key_level_snapshots_engine_version", ["engine_version"]),
        ("ix_key_level_snapshots_data_quality", ["data_quality"]),
        ("ix_key_level_snapshots_created_at", ["created_at"]),
        ("ix_key_level_snapshots_updated_at", ["updated_at"]),
        ("ix_key_level_snapshots_latest", ["scope", "cache_key", "trade_date"]),
        ("ix_key_level_snapshots_symbol_day", ["symbol", "trade_date"]),
    ):
        op.create_index(index_name, "key_level_snapshots", columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "key_level_snapshots" not in set(inspector.get_table_names()):
        return
    existing_indexes = {index["name"] for index in inspector.get_indexes("key_level_snapshots")}
    for index_name in (
        "ix_key_level_snapshots_symbol_day",
        "ix_key_level_snapshots_latest",
        "ix_key_level_snapshots_updated_at",
        "ix_key_level_snapshots_created_at",
        "ix_key_level_snapshots_data_quality",
        "ix_key_level_snapshots_engine_version",
        "ix_key_level_snapshots_trade_date",
        "ix_key_level_snapshots_symbol",
        "ix_key_level_snapshots_cache_key",
        "ix_key_level_snapshots_scope",
    ):
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name="key_level_snapshots")
    op.drop_table("key_level_snapshots")
