"""widen strategy tracking snapshot payload columns

Revision ID: 20260529_0002
Revises: 20260529_0001
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision = "20260529_0002"
down_revision = "20260529_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    inspector = sa.inspect(bind)
    if "strategy_tracking_snapshots" not in set(inspector.get_table_names()):
        return
    op.alter_column(
        "strategy_tracking_snapshots",
        "payload_json",
        existing_type=sa.Text(),
        type_=mysql.LONGTEXT().with_variant(sa.Text(), "sqlite"),
        existing_nullable=False,
    )
    op.alter_column(
        "strategy_tracking_snapshots",
        "metrics_json",
        existing_type=sa.Text(),
        type_=mysql.LONGTEXT().with_variant(sa.Text(), "sqlite"),
        existing_nullable=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    inspector = sa.inspect(bind)
    if "strategy_tracking_snapshots" not in set(inspector.get_table_names()):
        return
    op.alter_column(
        "strategy_tracking_snapshots",
        "metrics_json",
        existing_type=mysql.LONGTEXT(),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column(
        "strategy_tracking_snapshots",
        "payload_json",
        existing_type=mysql.LONGTEXT(),
        type_=sa.Text(),
        existing_nullable=False,
    )
