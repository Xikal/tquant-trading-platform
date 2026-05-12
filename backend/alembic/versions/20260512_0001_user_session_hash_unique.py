"""harden user session refresh token hash uniqueness

Revision ID: 20260512_0001
Revises: 20260509_0003
Create Date: 2026-05-12 09:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260512_0001"
down_revision = "20260509_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "user_sessions" not in inspector.get_table_names():
        return
    _raise_on_duplicate_hashes(bind)
    if _has_refresh_hash_unique(inspector):
        return
    op.create_index(
        "ux_user_sessions_refresh_token_hash",
        "user_sessions",
        ["refresh_token_hash"],
        unique=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "user_sessions" not in inspector.get_table_names():
        return
    indexes = {item["name"] for item in inspector.get_indexes("user_sessions")}
    if "ux_user_sessions_refresh_token_hash" in indexes:
        op.drop_index("ux_user_sessions_refresh_token_hash", table_name="user_sessions")


def _raise_on_duplicate_hashes(bind) -> None:
    duplicate_count = bind.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM (
                SELECT refresh_token_hash
                FROM user_sessions
                WHERE refresh_token_hash IS NOT NULL AND refresh_token_hash <> ''
                GROUP BY refresh_token_hash
                HAVING COUNT(*) > 1
            ) duplicated
            """
        )
    ).scalar()
    if int(duplicate_count or 0) > 0:
        raise RuntimeError(
            "user_sessions.refresh_token_hash contains duplicates; revoke duplicate sessions before migration"
        )


def _has_refresh_hash_unique(inspector) -> bool:
    for item in inspector.get_unique_constraints("user_sessions"):
        if item.get("column_names") == ["refresh_token_hash"]:
            return True
    for item in inspector.get_indexes("user_sessions"):
        if item.get("unique") and item.get("column_names") == ["refresh_token_hash"]:
            return True
    return False
