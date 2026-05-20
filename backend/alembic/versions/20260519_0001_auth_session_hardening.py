"""harden auth session token version

Revision ID: 20260519_0001_auth_hardening
Revises: 20260517_0003_ncore
Create Date: 2026-05-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260519_0001_auth_hardening"
down_revision = "20260517_0003_ncore"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "token_version" not in columns:
        op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
    bind.execute(sa.text("UPDATE users SET token_version = 0 WHERE token_version IS NULL"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "token_version" in columns:
        op.drop_column("users", "token_version")
