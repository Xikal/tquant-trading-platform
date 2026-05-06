"""phase3 gap fixes for presets and owner isolation

Revision ID: 20260506_0001
Revises: 20260505_0001
Create Date: 2026-05-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260506_0001"
down_revision = "20260505_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "strategy_presets" in tables:
        columns = {column["name"] for column in inspector.get_columns("strategy_presets")}
        if "preset_key" not in columns:
            op.add_column("strategy_presets", sa.Column("preset_key", sa.String(length=40), nullable=True))
        indexes = {index["name"] for index in inspector.get_indexes("strategy_presets")}
        if "ix_strategy_presets_preset_key" not in indexes:
            op.create_index("ix_strategy_presets_preset_key", "strategy_presets", ["preset_key"], unique=True)

    if "users" in tables:
        system_user_id = _ensure_system_user(bind)
    else:
        system_user_id = None

    for table_name in ("backtest_runs", "backtest_optimizations", "backtest_validations"):
        if table_name in tables and system_user_id is not None:
            bind.execute(
                sa.text(f"UPDATE {table_name} SET owner_user_id = :user_id WHERE owner_user_id IS NULL"),
                {"user_id": system_user_id},
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "strategy_presets" in tables:
        indexes = {index["name"] for index in inspector.get_indexes("strategy_presets")}
        if "ix_strategy_presets_preset_key" in indexes:
            op.drop_index("ix_strategy_presets_preset_key", table_name="strategy_presets")
        columns = {column["name"] for column in inspector.get_columns("strategy_presets")}
        if "preset_key" in columns:
            op.drop_column("strategy_presets", "preset_key")


def _ensure_system_user(bind) -> int:
    existing_id = bind.execute(sa.text("SELECT id FROM users WHERE username = 'system' LIMIT 1")).scalar()
    if existing_id is not None:
        return int(existing_id)
    bind.execute(
        sa.text(
            """
            INSERT INTO users (username, display_name, password_hash, is_active, can_paper_trade, roles)
            VALUES ('system', '系统管理员', 'disabled-system-user', 0, 0, 'admin')
            """
        )
    )
    created_id = bind.execute(sa.text("SELECT id FROM users WHERE username = 'system' LIMIT 1")).scalar()
    return int(created_id)
