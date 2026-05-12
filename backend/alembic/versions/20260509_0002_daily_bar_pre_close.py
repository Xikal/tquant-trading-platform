"""add daily bar previous close column

Revision ID: 20260509_0002
Revises: 20260509_0001
Create Date: 2026-05-09 10:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260509_0002"
down_revision = "20260509_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("daily_bar_snapshots")}
    if "pre_close" not in columns:
        op.add_column(
            "daily_bar_snapshots",
            sa.Column("pre_close", sa.Float(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("daily_bar_snapshots")}
    if "pre_close" in columns:
        op.drop_column("daily_bar_snapshots", "pre_close")
