"""widen system settings value for monitor snapshot cache

Revision ID: 20260508_0001
Revises: 20260507_0003
Create Date: 2026-05-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision = "20260508_0001"
down_revision = "20260507_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "system_settings" not in set(inspector.get_table_names()):
        return
    if bind.dialect.name == "mysql":
        op.alter_column(
            "system_settings",
            "value",
            existing_type=sa.Text(),
            type_=mysql.LONGTEXT(),
            existing_nullable=True,
        )


def downgrade() -> None:
    # Do not shrink back to TEXT automatically: monitor snapshots and cached
    # settings can legitimately exceed 64 KiB on MySQL.
    return
