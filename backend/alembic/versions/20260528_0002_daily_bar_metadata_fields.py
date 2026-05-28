"""add daily bar metadata fields

Revision ID: 20260528_0002
Revises: 20260528_0001
Create Date: 2026-05-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260528_0002"
down_revision = "20260528_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "daily_bar_snapshots" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("daily_bar_snapshots")}
    _add_column_if_missing("daily_bar_snapshots", columns, sa.Column("source", sa.String(48), nullable=False, server_default="unknown"))
    _add_column_if_missing("daily_bar_snapshots", columns, sa.Column("fetch_time", sa.String(32), nullable=False, server_default=""))
    _add_column_if_missing("daily_bar_snapshots", columns, sa.Column("adjusted_mode", sa.String(16), nullable=False, server_default="unknown"))
    _add_column_if_missing("daily_bar_snapshots", columns, sa.Column("checksum", sa.String(64), nullable=False, server_default=""))
    _add_column_if_missing("daily_bar_snapshots", columns, sa.Column("data_quality", sa.String(24), nullable=False, server_default="unknown"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "daily_bar_snapshots" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("daily_bar_snapshots")}
    for column in ("data_quality", "checksum", "adjusted_mode", "fetch_time", "source"):
        if column in columns:
            op.drop_column("daily_bar_snapshots", column)


def _add_column_if_missing(table: str, columns: set[str], column: sa.Column) -> None:
    if column.name not in columns:
        op.add_column(table, column)
        columns.add(column.name)
