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
    op.alter_column(
        "low_buy_result_snapshots",
        "buy_signal_state",
        existing_type=sa.String(length=16),
        type_=sa.String(length=32),
        existing_nullable=True,
        existing_server_default=None,
    )


def downgrade() -> None:
    op.execute(
        "UPDATE low_buy_result_snapshots "
        "SET buy_signal_state = 'near_entry' "
        "WHERE buy_signal_state = 'observe_confirmed'"
    )
    op.alter_column(
        "low_buy_result_snapshots",
        "buy_signal_state",
        existing_type=sa.String(length=32),
        type_=sa.String(length=16),
        existing_nullable=True,
        existing_server_default=None,
    )
