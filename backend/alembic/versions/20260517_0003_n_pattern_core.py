"""Promote N-pattern strategies to core production tier.

Revision ID: 20260517_0003_ncore
Revises: 20260517_0002_nprod
Create Date: 2026-05-17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260517_0003_ncore"
down_revision = "20260517_0002_nprod"
branch_labels = None
depends_on = None

def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "strategy_metadata" in tables:
        bind.execute(
            sa.text(
                """
                UPDATE strategy_metadata
                SET category='core', enabled=1, visibility='full', probe_status='not_required'
                WHERE `key` IN ('n_pattern_long_wash', 'n_pattern_short_wash')
                """
            )
        )
    if "strategy_tier_overrides" in tables:
        bind.execute(
            sa.text(
                """
                UPDATE strategy_tier_overrides
                SET override_tier='core', reverted_at=NULL
                WHERE strategy_key IN ('n_pattern_long_wash', 'n_pattern_short_wash')
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "strategy_metadata" in tables:
        bind.execute(
            sa.text(
                """
                UPDATE strategy_metadata
                SET category='auxiliary'
                WHERE `key` IN ('n_pattern_long_wash', 'n_pattern_short_wash')
                """
            )
        )
    if "strategy_tier_overrides" in tables:
        bind.execute(
            sa.text(
                """
                UPDATE strategy_tier_overrides
                SET override_tier='auxiliary'
                WHERE strategy_key IN ('n_pattern_long_wash', 'n_pattern_short_wash')
                """
            )
        )
