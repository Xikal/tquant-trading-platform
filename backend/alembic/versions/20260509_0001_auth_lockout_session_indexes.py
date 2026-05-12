"""add auth lockout columns and session lookup index

Revision ID: 20260509_0001
Revises: 20260508_0004
Create Date: 2026-05-09 09:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260509_0001"
down_revision = "20260508_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "failed_login_count" not in user_columns:
        op.add_column("users", sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"))
    if "locked_until" not in user_columns:
        op.add_column("users", sa.Column("locked_until", sa.DateTime(), nullable=True))
    if "last_failed_login_at" not in user_columns:
        op.add_column("users", sa.Column("last_failed_login_at", sa.DateTime(), nullable=True))

    indexes = {index["name"] for index in inspector.get_indexes("users")}
    if "ix_users_locked_until" not in indexes:
        op.create_index("ix_users_locked_until", "users", ["locked_until"])

    session_indexes = {index["name"] for index in inspector.get_indexes("user_sessions")}
    if "ix_user_sessions_user_revoked_expires" not in session_indexes:
        op.create_index(
            "ix_user_sessions_user_revoked_expires",
            "user_sessions",
            ["user_id", "revoked_at", "expires_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_indexes = {index["name"] for index in inspector.get_indexes("users")}
    if "ix_users_locked_until" in user_indexes:
        op.drop_index("ix_users_locked_until", table_name="users")
    session_indexes = {index["name"] for index in inspector.get_indexes("user_sessions")}
    if "ix_user_sessions_user_revoked_expires" in session_indexes:
        op.drop_index("ix_user_sessions_user_revoked_expires", table_name="user_sessions")
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    for column in ("last_failed_login_at", "locked_until", "failed_login_count"):
        if column in user_columns:
            op.drop_column("users", column)
