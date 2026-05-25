"""daily bar snapshot date and decimal precision

Revision ID: 20260523_0001_daily_bar_decimal_date
Revises: 20260519_0002_encrypt_settings
Create Date: 2026-05-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260523_0001_daily_bar_decimal_date"
down_revision = "20260519_0002_encrypt_settings"
branch_labels = None
depends_on = None

_PRICE_COLUMNS = ("open_price", "close_price", "high_price", "low_price")


def upgrade() -> None:
    bind = op.get_bind()
    if "daily_bar_snapshots" not in sa.inspect(bind).get_table_names():
        return
    if bind.dialect.name == "sqlite":
        _upgrade_sqlite()
        return
    op.alter_column(
        "daily_bar_snapshots",
        "trade_date",
        existing_type=sa.String(length=16),
        type_=sa.Date(),
        existing_nullable=True,
    )
    for column in _PRICE_COLUMNS:
        op.alter_column(
            "daily_bar_snapshots",
            column,
            existing_type=sa.Float(),
            type_=sa.Numeric(18, 4),
            existing_nullable=True,
        )
    op.alter_column(
        "daily_bar_snapshots",
        "volume",
        existing_type=sa.Float(),
        type_=sa.Numeric(20, 0),
        existing_nullable=True,
    )
    op.alter_column(
        "daily_bar_snapshots",
        "amount",
        existing_type=sa.Float(),
        type_=sa.Numeric(20, 2),
        existing_nullable=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    if "daily_bar_snapshots" not in sa.inspect(bind).get_table_names():
        return
    if bind.dialect.name == "sqlite":
        _downgrade_sqlite()
        return
    op.alter_column(
        "daily_bar_snapshots",
        "trade_date",
        existing_type=sa.Date(),
        type_=sa.String(length=16),
        existing_nullable=True,
    )
    for column in _PRICE_COLUMNS:
        op.alter_column(
            "daily_bar_snapshots",
            column,
            existing_type=sa.Numeric(18, 4),
            type_=sa.Float(),
            existing_nullable=True,
        )
    op.alter_column(
        "daily_bar_snapshots",
        "volume",
        existing_type=sa.Numeric(20, 0),
        type_=sa.Float(),
        existing_nullable=True,
    )
    op.alter_column(
        "daily_bar_snapshots",
        "amount",
        existing_type=sa.Numeric(20, 2),
        type_=sa.Float(),
        existing_nullable=True,
    )


def _upgrade_sqlite() -> None:
    with op.batch_alter_table("daily_bar_snapshots") as batch:
        batch.alter_column("trade_date", existing_type=sa.String(length=16), type_=sa.Date())
        for column in _PRICE_COLUMNS:
            batch.alter_column(column, existing_type=sa.Float(), type_=sa.Numeric(18, 4))
        batch.alter_column("volume", existing_type=sa.Float(), type_=sa.Numeric(20, 0))
        batch.alter_column("amount", existing_type=sa.Float(), type_=sa.Numeric(20, 2))


def _downgrade_sqlite() -> None:
    with op.batch_alter_table("daily_bar_snapshots") as batch:
        batch.alter_column("trade_date", existing_type=sa.Date(), type_=sa.String(length=16))
        for column in _PRICE_COLUMNS:
            batch.alter_column(column, existing_type=sa.Numeric(18, 4), type_=sa.Float())
        batch.alter_column("volume", existing_type=sa.Numeric(20, 0), type_=sa.Float())
        batch.alter_column("amount", existing_type=sa.Numeric(20, 2), type_=sa.Float())
