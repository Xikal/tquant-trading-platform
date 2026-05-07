"""persist market regime snapshots

Revision ID: 20260507_0001
Revises: 20260506_0003
Create Date: 2026-05-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260507_0001"
down_revision = "20260506_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "market_regime_snapshots" in tables:
        return
    op.create_table(
        "market_regime_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cache_key", sa.String(length=120), nullable=False),
        sa.Column("trade_date", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("state", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("breadth_ready", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("emotion_ready", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("hot_industry_source", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("data_quality", sa.String(length=24), nullable=False, server_default="limited"),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.UniqueConstraint("cache_key", name="uq_market_regime_snapshot_cache_key"),
    )
    op.create_index("ix_market_regime_snapshots_cache_key", "market_regime_snapshots", ["cache_key"])
    op.create_index("ix_market_regime_snapshots_trade_date", "market_regime_snapshots", ["trade_date"])
    op.create_index("ix_market_regime_snapshots_state", "market_regime_snapshots", ["state"])
    op.create_index("ix_market_regime_snapshots_readiness", "market_regime_snapshots", ["breadth_ready", "emotion_ready"])
    op.create_index("ix_market_regime_snapshots_source", "market_regime_snapshots", ["hot_industry_source"])
    op.create_index("ix_market_regime_snapshots_quality", "market_regime_snapshots", ["data_quality"])
    op.create_index("ix_market_regime_snapshots_updated", "market_regime_snapshots", ["updated_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "market_regime_snapshots" not in set(inspector.get_table_names()):
        return
    for index_name in (
        "ix_market_regime_snapshots_updated",
        "ix_market_regime_snapshots_quality",
        "ix_market_regime_snapshots_source",
        "ix_market_regime_snapshots_readiness",
        "ix_market_regime_snapshots_state",
        "ix_market_regime_snapshots_trade_date",
        "ix_market_regime_snapshots_cache_key",
    ):
        if index_name in {item["name"] for item in inspector.get_indexes("market_regime_snapshots")}:
            op.drop_index(index_name, table_name="market_regime_snapshots")
    op.drop_table("market_regime_snapshots")
