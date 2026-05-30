"""add tick trade snapshots

Revision ID: 20260530_0001
Revises: 20260529_0002
Create Date: 2026-05-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260530_0001"
down_revision = "20260529_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "tick_trade_snapshots" not in tables:
        op.create_table(
            "tick_trade_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("symbol", sa.String(16), nullable=False, index=True),
            sa.Column("market", sa.String(16), nullable=False, server_default="CN"),
            sa.Column("instrument_type", sa.String(16), nullable=False, server_default="stock", index=True),
            sa.Column("trade_date", sa.Date(), nullable=True, index=True),
            sa.Column("trade_timestamp", sa.String(32), nullable=False, index=True),
            sa.Column("price", sa.Float(), nullable=False, server_default="0"),
            sa.Column("volume", sa.Float(), nullable=False, server_default="0"),
            sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
            sa.Column("side", sa.String(12), nullable=False, server_default=""),
            sa.Column("source", sa.String(48), nullable=False, server_default="unknown", index=True),
            sa.Column("fetch_time", sa.String(32), nullable=False, server_default="", index=True),
            sa.Column("data_quality", sa.String(24), nullable=False, server_default="unknown", index=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("symbol", "source", "trade_timestamp", "price", "volume", name="uq_tick_trade_snapshot"),
        )
    index_names = {index["name"] for index in inspector.get_indexes("tick_trade_snapshots")}
    if "ix_tick_symbol_trade_date" not in index_names:
        op.create_index("ix_tick_symbol_trade_date", "tick_trade_snapshots", ["symbol", "trade_date"])
    if "ix_tick_symbol_timestamp" not in index_names:
        op.create_index("ix_tick_symbol_timestamp", "tick_trade_snapshots", ["symbol", "trade_timestamp"])
    if "ix_tick_source_quality" not in index_names:
        op.create_index("ix_tick_source_quality", "tick_trade_snapshots", ["source", "data_quality"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tick_trade_snapshots" not in set(inspector.get_table_names()):
        return
    index_names = {index["name"] for index in inspector.get_indexes("tick_trade_snapshots")}
    for index_name in ("ix_tick_source_quality", "ix_tick_symbol_timestamp", "ix_tick_symbol_trade_date"):
        if index_name in index_names:
            op.drop_index(index_name, table_name="tick_trade_snapshots")
    op.drop_table("tick_trade_snapshots")
