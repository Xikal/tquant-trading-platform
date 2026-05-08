"""add market model observation tracking

Revision ID: 20260508_0003
Revises: 20260508_0002
Create Date: 2026-05-08 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260508_0003"
down_revision = "20260508_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_model_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_key", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("name", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("trade_date", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("signal_state", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("expected_edge_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("outcome_status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "model_key",
            "symbol",
            "trade_date",
            "signal_state",
            name="uq_market_model_observation_signal_day",
        ),
    )
    op.create_index("ix_market_model_observations_model_key", "market_model_observations", ["model_key"])
    op.create_index("ix_market_model_observations_symbol", "market_model_observations", ["symbol"])
    op.create_index("ix_market_model_observations_trade_date", "market_model_observations", ["trade_date"])
    op.create_index("ix_market_model_observations_signal_state", "market_model_observations", ["signal_state"])
    op.create_index("ix_market_model_observations_outcome_status", "market_model_observations", ["outcome_status"])
    op.create_index("ix_market_model_observations_observed_at", "market_model_observations", ["observed_at"])
    op.create_index(
        "ix_market_model_observations_model_date",
        "market_model_observations",
        ["model_key", "trade_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_model_observations_model_date", table_name="market_model_observations")
    op.drop_index("ix_market_model_observations_observed_at", table_name="market_model_observations")
    op.drop_index("ix_market_model_observations_outcome_status", table_name="market_model_observations")
    op.drop_index("ix_market_model_observations_signal_state", table_name="market_model_observations")
    op.drop_index("ix_market_model_observations_trade_date", table_name="market_model_observations")
    op.drop_index("ix_market_model_observations_symbol", table_name="market_model_observations")
    op.drop_index("ix_market_model_observations_model_key", table_name="market_model_observations")
    op.drop_table("market_model_observations")
