"""Promote N-pattern strategies to production auxiliary tier.

Revision ID: 20260517_0002_nprod
Revises: 20260517_0001_obs_state
Create Date: 2026-05-17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260517_0002_nprod"
down_revision = "20260517_0001_obs_state"
branch_labels = None
depends_on = None


N_PATTERN_ROWS = (
    {
        "key": "n_pattern_long_wash",
        "display_name": "长洗N字冲高",
        "description": "大阳/涨停启动后 7-15 日缩量洗盘，守住启动低点后放量修复，主要做 3-5 日冲高止盈。",
        "holding_days": "3-5天冲高止盈",
        "sort_order": 90,
    },
    {
        "key": "n_pattern_short_wash",
        "display_name": "短洗N字冲高",
        "description": "启动后 2-5 日快速分歧，红十字或锤头线守住启动低点，主要做 T+1/T+2 冲高止盈。",
        "holding_days": "1-2天冲高止盈",
        "sort_order": 100,
    },
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "strategy_metadata" in tables:
        for row in N_PATTERN_ROWS:
            exists = bind.execute(
                sa.text("SELECT 1 FROM strategy_metadata WHERE `key` = :key LIMIT 1"),
                {"key": row["key"]},
            ).scalar()
            if exists:
                bind.execute(
                    sa.text(
                        """
                        UPDATE strategy_metadata
                        SET display_name=:display_name,
                            description=:description,
                            category='auxiliary',
                            typical_holding_days=:holding_days,
                            enabled=1,
                            probe_status='not_required',
                            probe_summary='',
                            visibility='full'
                        WHERE `key`=:key
                        """
                    ),
                    row,
                )
                continue
            bind.execute(
                sa.text(
                    """
                    INSERT INTO strategy_metadata (
                        `key`, display_name, description, category, risk_level,
                        typical_holding_days, sort_order, enabled, probe_status,
                        probe_summary, visibility
                    )
                    VALUES (
                        :key, :display_name, :description, 'auxiliary', 'high',
                        :holding_days, :sort_order, 1, 'not_required', '', 'full'
                    )
                    """
                ),
                row,
            )
    if "strategy_tier_overrides" in tables:
        bind.execute(
            sa.text(
                """
                UPDATE strategy_tier_overrides
                SET override_tier='auxiliary', reverted_at=NULL
                WHERE strategy_key IN ('n_pattern_long_wash', 'n_pattern_short_wash')
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "strategy_metadata" in tables:
        bind.execute(
            sa.text(
                """
                UPDATE strategy_metadata
                SET category='research'
                WHERE `key` IN ('n_pattern_long_wash', 'n_pattern_short_wash')
                """
            )
        )
