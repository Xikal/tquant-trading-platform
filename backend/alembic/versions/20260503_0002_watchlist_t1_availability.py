"""watchlist T+1 availability date

Revision ID: 20260503_0002
Revises: 20260503_0001
Create Date: 2026-05-03
"""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20260503_0002"
down_revision = "20260503_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    _ensure_columns(
        inspector=inspector,
        specs=(
            ("watchlist", "available_position_date"),
            ("user_watchlists", "available_position_date"),
        ),
    )
    _ensure_indexes(
        inspector=sa.inspect(bind),
        specs=(
            ("watchlist", "ix_watchlist_available_position_date", ("available_position_date",)),
            ("user_watchlists", "ix_user_watchlists_available_position_date", ("available_position_date",)),
        ),
    )


def downgrade() -> None:
    pass


def _ensure_columns(*, inspector, specs: Sequence[tuple[str, str]]) -> None:
    tables = set(inspector.get_table_names())
    for table_name, column_name in specs:
        if table_name not in tables:
            continue
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if column_name not in columns:
            op.add_column(table_name, sa.Column(column_name, sa.Date(), nullable=True))


def _ensure_indexes(*, inspector, specs: Sequence[tuple[str, str, tuple[str, ...]]]) -> None:
    tables = set(inspector.get_table_names())
    for table_name, index_name, columns in specs:
        if table_name not in tables:
            continue
        existing = {item["name"] for item in inspector.get_indexes(table_name)}
        if index_name not in existing:
            op.create_index(index_name, table_name, list(columns))
