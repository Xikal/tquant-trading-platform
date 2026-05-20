"""Allow observe_confirmed low-buy signal state.

Revision ID: 20260517_0001_obs_state
Revises: 20260516_0001_factor_mining
Create Date: 2026-05-17 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260517_0001_obs_state"
down_revision = "20260516_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not _table_exists("low_buy_result_snapshots"):
        return
    with op.batch_alter_table("low_buy_result_snapshots") as batch_op:
        batch_op.alter_column(
            "buy_signal_state",
            existing_type=sa.String(length=16),
            type_=sa.String(length=32),
            existing_nullable=True,
            existing_server_default=None,
        )


def downgrade() -> None:
    if not _table_exists("low_buy_result_snapshots"):
        return
    op.execute(
        "UPDATE low_buy_result_snapshots "
        "SET buy_signal_state = 'near_entry' "
        "WHERE buy_signal_state = 'observe_confirmed'"
    )
    with op.batch_alter_table("low_buy_result_snapshots") as batch_op:
        batch_op.alter_column(
            "buy_signal_state",
            existing_type=sa.String(length=32),
            type_=sa.String(length=16),
            existing_nullable=True,
            existing_server_default=None,
        )


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    return table_name in sa.inspect(bind).get_table_names()
