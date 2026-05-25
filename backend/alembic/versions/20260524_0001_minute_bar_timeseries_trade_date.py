"""add trade-date partition key for minute bar snapshots

Revision ID: 20260524_0001
Revises: 20260523_0001
Create Date: 2026-05-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260524_0001"
down_revision = "20260523_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "minute_bar_snapshots" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("minute_bar_snapshots")}
    if "trade_date" not in columns:
        op.add_column("minute_bar_snapshots", sa.Column("trade_date", sa.Date(), nullable=True))
    index_names = {index["name"] for index in inspector.get_indexes("minute_bar_snapshots")}
    if "ix_minute_trade_period_symbol_time" not in index_names:
        op.create_index(
            "ix_minute_trade_period_symbol_time",
            "minute_bar_snapshots",
            ["trade_date", "bar_period", "symbol", "bar_timestamp"],
        )
    if "ix_minute_symbol_trade_period_time" not in index_names:
        op.create_index(
            "ix_minute_symbol_trade_period_time",
            "minute_bar_snapshots",
            ["symbol", "trade_date", "bar_period", "bar_timestamp"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "minute_bar_snapshots" not in set(inspector.get_table_names()):
        return
    index_names = {index["name"] for index in inspector.get_indexes("minute_bar_snapshots")}
    for index_name in ("ix_minute_symbol_trade_period_time", "ix_minute_trade_period_symbol_time"):
        if index_name in index_names:
            op.drop_index(index_name, table_name="minute_bar_snapshots")
    columns = {column["name"] for column in inspector.get_columns("minute_bar_snapshots")}
    if "trade_date" in columns:
        op.drop_column("minute_bar_snapshots", "trade_date")
