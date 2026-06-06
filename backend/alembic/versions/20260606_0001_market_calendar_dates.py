"""add market calendar dates table

Revision ID: 20260606_0001
Revises: 20260603_0001
Create Date: 2026-06-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260606_0001"
down_revision = "20260603_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "market_calendar_dates" in set(inspector.get_table_names()):
        return
    op.create_table(
        "market_calendar_dates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("market", sa.String(length=16), nullable=False, server_default="CN"),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("is_trading_day", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("session_type", sa.String(length=24), nullable=False, server_default="regular"),
        sa.Column("source", sa.String(length=48), nullable=False, server_default="manual"),
        sa.Column("note", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("market", "trade_date", name="uq_market_calendar_date"),
    )
    for index_name, columns in (
        ("ix_market_calendar_dates_market", ["market"]),
        ("ix_market_calendar_dates_trade_date", ["trade_date"]),
        ("ix_market_calendar_dates_is_trading_day", ["is_trading_day"]),
        ("ix_market_calendar_dates_session_type", ["session_type"]),
        ("ix_market_calendar_dates_source", ["source"]),
        ("ix_market_calendar_dates_market_trade_date", ["market", "trade_date"]),
    ):
        op.create_index(index_name, "market_calendar_dates", columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "market_calendar_dates" not in set(inspector.get_table_names()):
        return
    existing_indexes = {index["name"] for index in inspector.get_indexes("market_calendar_dates")}
    for index_name in (
        "ix_market_calendar_dates_market_trade_date",
        "ix_market_calendar_dates_source",
        "ix_market_calendar_dates_session_type",
        "ix_market_calendar_dates_is_trading_day",
        "ix_market_calendar_dates_trade_date",
        "ix_market_calendar_dates_market",
    ):
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name="market_calendar_dates")
    op.drop_table("market_calendar_dates")
