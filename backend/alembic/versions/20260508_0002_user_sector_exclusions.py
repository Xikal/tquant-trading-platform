"""add user sector exclusion preferences

Revision ID: 20260508_0002
Revises: 20260508_0001
Create Date: 2026-05-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260508_0002"
down_revision = "20260508_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "user_sector_exclusions" in set(inspector.get_table_names()):
        return
    op.create_table(
        "user_sector_exclusions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("sector_name", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.UniqueConstraint("user_id", "sector_name", name="uq_user_sector_exclusion_user_sector"),
    )
    op.create_index("ix_user_sector_exclusions_user_id", "user_sector_exclusions", ["user_id"])
    op.create_index("ix_user_sector_exclusions_sector_name", "user_sector_exclusions", ["sector_name"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "user_sector_exclusions" not in set(inspector.get_table_names()):
        return
    op.drop_index("ix_user_sector_exclusions_sector_name", table_name="user_sector_exclusions")
    op.drop_index("ix_user_sector_exclusions_user_id", table_name="user_sector_exclusions")
    op.drop_table("user_sector_exclusions")
