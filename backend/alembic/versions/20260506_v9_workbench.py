"""v9 strategy workbench governance and elasticity cache

Revision ID: 20260506_v9_workbench
Revises: 20260506_0001
Create Date: 2026-05-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260506_v9_workbench"
down_revision = "20260506_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "strategy_metadata" in tables:
        _ensure_strategy_metadata_columns(inspector)
        _seed_strategy_metadata(bind)

    if "strategy_tier_overrides" not in tables:
        op.create_table(
            "strategy_tier_overrides",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("strategy_key", sa.String(length=80), nullable=False),
            sa.Column("override_tier", sa.String(length=20), nullable=False, server_default="research"),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("evidence_summary", sa.Text(), nullable=True),
            sa.Column("operator_user_id", sa.Integer(), nullable=True),
            sa.Column("promoted_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.Column("reverted_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.UniqueConstraint("strategy_key", name="uq_strategy_tier_override_key"),
        )
        op.create_index("ix_strategy_tier_overrides_strategy_key", "strategy_tier_overrides", ["strategy_key"])
        op.create_index("ix_strategy_tier_overrides_override_tier", "strategy_tier_overrides", ["override_tier"])
        op.create_index("ix_strategy_tier_overrides_reverted_at", "strategy_tier_overrides", ["reverted_at"])

    if "strategy_tier_override_log" not in tables:
        op.create_table(
            "strategy_tier_override_log",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("strategy_key", sa.String(length=80), nullable=False),
            sa.Column("action", sa.String(length=20), nullable=False, server_default=""),
            sa.Column("from_tier", sa.String(length=20), nullable=True),
            sa.Column("to_tier", sa.String(length=20), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("evidence_summary", sa.Text(), nullable=True),
            sa.Column("operator_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        )
        op.create_index("ix_strategy_tier_override_log_strategy_key", "strategy_tier_override_log", ["strategy_key"])
        op.create_index("ix_strategy_tier_override_log_action", "strategy_tier_override_log", ["action"])

    if "trading_elasticity_cache" not in tables:
        op.create_table(
            "trading_elasticity_cache",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("symbol", sa.String(length=16), nullable=False),
            sa.Column("elasticity_score", sa.Float(), nullable=True, server_default="10"),
            sa.Column("elasticity_tier", sa.String(length=12), nullable=True, server_default="★★"),
            sa.Column("data_quality", sa.String(length=24), nullable=True, server_default="unavailable"),
            sa.Column("sample_count", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("payload_json", sa.Text(), nullable=True),
            sa.Column("computed_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.UniqueConstraint("symbol", name="uq_trading_elasticity_symbol"),
        )
        op.create_index("ix_trading_elasticity_cache_symbol", "trading_elasticity_cache", ["symbol"])
        op.create_index("ix_trading_elasticity_cache_data_quality", "trading_elasticity_cache", ["data_quality"])

    if "feature_flag_audit_log" not in tables:
        op.create_table(
            "feature_flag_audit_log",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("flag_key", sa.String(length=64), nullable=False),
            sa.Column("old_value", sa.Text(), nullable=True),
            sa.Column("new_value", sa.Text(), nullable=True),
            sa.Column("operator_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        )
        op.create_index("ix_feature_flag_audit_log_flag_key", "feature_flag_audit_log", ["flag_key"])


def downgrade() -> None:
    for table_name in (
        "feature_flag_audit_log",
        "trading_elasticity_cache",
        "strategy_tier_override_log",
        "strategy_tier_overrides",
    ):
        op.drop_table(table_name)


def _ensure_strategy_metadata_columns(inspector) -> None:
    columns = {column["name"] for column in inspector.get_columns("strategy_metadata")}
    if "enabled" not in columns:
        op.add_column("strategy_metadata", sa.Column("enabled", sa.Boolean(), nullable=True, server_default=sa.true()))
    if "probe_status" not in columns:
        op.add_column("strategy_metadata", sa.Column("probe_status", sa.String(length=20), nullable=True, server_default="not_required"))
    if "probe_summary" not in columns:
        op.add_column("strategy_metadata", sa.Column("probe_summary", sa.Text(), nullable=True))
    if "visibility" not in columns:
        op.add_column("strategy_metadata", sa.Column("visibility", sa.String(length=20), nullable=True, server_default="full"))


def _seed_strategy_metadata(bind) -> None:
    seeds = [
        ("ma_channel_band", "均线通道波段", "沿 MA20 通道运行的波段研究策略，关注下轨承接与上轨兑现。", "research", "medium", "5-15天", 60, 1, "not_required", "", "full"),
        ("leader_pullback_band", "龙头回踩波段", "热点龙头确认后回踩均线支撑的二波研究策略。", "research", "high", "3-10天", 70, 1, "pending", "待样本外验证完成后开放生产入口。", "backtest_only"),
    ]
    for seed in seeds:
        exists = bind.execute(sa.text("SELECT 1 FROM strategy_metadata WHERE key = :key LIMIT 1"), {"key": seed[0]}).scalar()
        if exists:
            bind.execute(
                sa.text(
                    """
                    UPDATE strategy_metadata
                    SET category=:category, enabled=:enabled, probe_status=:probe_status,
                        probe_summary=:probe_summary, visibility=:visibility
                    WHERE key=:key
                    """
                ),
                {
                    "key": seed[0],
                    "category": seed[3],
                    "enabled": seed[7],
                    "probe_status": seed[8],
                    "probe_summary": seed[9],
                    "visibility": seed[10],
                },
            )
            continue
        bind.execute(
            sa.text(
                """
                INSERT INTO strategy_metadata (
                    key, display_name, description, category, risk_level,
                    typical_holding_days, sort_order, enabled, probe_status,
                    probe_summary, visibility
                )
                VALUES (
                    :key, :display_name, :description, :category, :risk_level,
                    :holding_days, :sort_order, :enabled, :probe_status,
                    :probe_summary, :visibility
                )
                """
            ),
            {
                "key": seed[0],
                "display_name": seed[1],
                "description": seed[2],
                "category": seed[3],
                "risk_level": seed[4],
                "holding_days": seed[5],
                "sort_order": seed[6],
                "enabled": seed[7],
                "probe_status": seed[8],
                "probe_summary": seed[9],
                "visibility": seed[10],
            },
        )
