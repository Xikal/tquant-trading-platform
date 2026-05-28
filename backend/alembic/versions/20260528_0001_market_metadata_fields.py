"""add market metadata fields for strategy acceptance gates

Revision ID: 20260528_0001
Revises: 20260526_0002
Create Date: 2026-05-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260528_0001"
down_revision = "20260526_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "instruments" in tables:
        columns = {column["name"] for column in inspector.get_columns("instruments")}
        _add_column_if_missing("instruments", columns, sa.Column("listing_date", sa.Date(), nullable=True))
        _add_column_if_missing("instruments", columns, sa.Column("delisting_date", sa.Date(), nullable=True))
        _add_column_if_missing("instruments", columns, sa.Column("is_st", sa.Boolean(), nullable=False, server_default=sa.false()))
        _add_column_if_missing("instruments", columns, sa.Column("status", sa.String(24), nullable=False, server_default="active"))
    if "daily_bar_snapshots" in tables:
        columns = {column["name"] for column in inspector.get_columns("daily_bar_snapshots")}
        _add_column_if_missing("daily_bar_snapshots", columns, sa.Column("limit_up_price", sa.Float(), nullable=False, server_default="0"))
        _add_column_if_missing("daily_bar_snapshots", columns, sa.Column("limit_down_price", sa.Float(), nullable=False, server_default="0"))
        _add_column_if_missing("daily_bar_snapshots", columns, sa.Column("is_suspended", sa.Boolean(), nullable=False, server_default=sa.false()))
        _add_column_if_missing("daily_bar_snapshots", columns, sa.Column("is_st", sa.Boolean(), nullable=False, server_default=sa.false()))
        _add_column_if_missing("daily_bar_snapshots", columns, sa.Column("is_delisted", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "minute_bar_snapshots" in tables:
        columns = {column["name"] for column in inspector.get_columns("minute_bar_snapshots")}
        _add_column_if_missing("minute_bar_snapshots", columns, sa.Column("bid_ask_spread", sa.Float(), nullable=False, server_default="0"))
        _add_column_if_missing("minute_bar_snapshots", columns, sa.Column("premium_discount_pct", sa.Float(), nullable=True))
        _add_column_if_missing("minute_bar_snapshots", columns, sa.Column("tracking_index_symbol", sa.String(32), nullable=False, server_default=""))
        _add_column_if_missing("minute_bar_snapshots", columns, sa.Column("liquidity_tier", sa.String(24), nullable=False, server_default="unknown"))
    if "instrument_industry_history" not in tables:
        _create_industry_history()
    if "instrument_concept_history" not in tables:
        _create_concept_history()


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "instrument_concept_history" in tables:
        op.drop_table("instrument_concept_history")
    if "instrument_industry_history" in tables:
        op.drop_table("instrument_industry_history")
    for table, columns in {
        "minute_bar_snapshots": ["liquidity_tier", "tracking_index_symbol", "premium_discount_pct", "bid_ask_spread"],
        "daily_bar_snapshots": ["is_delisted", "is_st", "is_suspended", "limit_down_price", "limit_up_price"],
        "instruments": ["status", "is_st", "delisting_date", "listing_date"],
    }.items():
        if table not in tables:
            continue
        existing = {column["name"] for column in inspector.get_columns(table)}
        for column in columns:
            if column in existing:
                op.drop_column(table, column)


def _add_column_if_missing(table: str, columns: set[str], column: sa.Column) -> None:
    if column.name not in columns:
        op.add_column(table, column)
        columns.add(column.name)


def _create_industry_history() -> None:
    op.create_table(
        "instrument_industry_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False, index=True),
        sa.Column("trade_date", sa.Date(), nullable=False, index=True),
        sa.Column("industry_name", sa.String(80), nullable=False, server_default="", index=True),
        sa.Column("source", sa.String(48), nullable=False, server_default="unknown", index=True),
        sa.Column("data_quality", sa.String(24), nullable=False, server_default="unknown", index=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("symbol", "trade_date", "industry_name", name="uq_instrument_industry_history_day"),
    )


def _create_concept_history() -> None:
    op.create_table(
        "instrument_concept_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False, index=True),
        sa.Column("trade_date", sa.Date(), nullable=False, index=True),
        sa.Column("concept_name", sa.String(80), nullable=False, server_default="", index=True),
        sa.Column("source", sa.String(48), nullable=False, server_default="unknown", index=True),
        sa.Column("data_quality", sa.String(24), nullable=False, server_default="unknown", index=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("symbol", "trade_date", "concept_name", name="uq_instrument_concept_history_day"),
    )
