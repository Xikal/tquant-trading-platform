"""strategy metadata and presets

Revision ID: 20260505_0001
Revises: 20260503_0002
Create Date: 2026-05-05
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op


revision = "20260505_0001"
down_revision = "20260503_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "strategy_metadata" not in tables:
        op.create_table(
            "strategy_metadata",
            sa.Column("key", sa.String(length=80), primary_key=True),
            sa.Column("display_name", sa.String(length=80), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("category", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("risk_level", sa.String(length=16), nullable=False, server_default="medium"),
            sa.Column("typical_holding_days", sa.String(length=24), nullable=False, server_default=""),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index("ix_strategy_metadata_sort_order", "strategy_metadata", ["sort_order"])
        op.bulk_insert(
            sa.table(
                "strategy_metadata",
                sa.column("key", sa.String),
                sa.column("display_name", sa.String),
                sa.column("description", sa.Text),
                sa.column("category", sa.String),
                sa.column("risk_level", sa.String),
                sa.column("typical_holding_days", sa.String),
                sa.column("sort_order", sa.Integer),
            ),
            [
                {
                    "key": "first_board",
                    "display_name": "首板回调",
                    "description": "首板启动后回调承接，偏事件低吸。",
                    "category": "生产策略",
                    "risk_level": "medium",
                    "typical_holding_days": "1-3天",
                    "sort_order": 10,
                },
                {
                    "key": "volume_shrink",
                    "display_name": "量能低吸",
                    "description": "放量启动后缩量回踩，等待承接修复。",
                    "category": "生产策略",
                    "risk_level": "medium",
                    "typical_holding_days": "1-3天",
                    "sort_order": 20,
                },
                {
                    "key": "late_session_strong_support",
                    "display_name": "收盘强势承接",
                    "description": "主线标的收盘仍有承接，关注次日冲高兑现。",
                    "category": "辅助策略",
                    "risk_level": "medium",
                    "typical_holding_days": "1-2天",
                    "sort_order": 30,
                },
                {
                    "key": "core_midcap_vwap_ma5_retrace",
                    "display_name": "中军回踩",
                    "description": "板块核心中军回踩均线/VWAP 附近的低吸观察。",
                    "category": "辅助策略",
                    "risk_level": "medium",
                    "typical_holding_days": "2-4天",
                    "sort_order": 40,
                },
                {
                    "key": "sector_mainline_first_divergence_low_buy",
                    "display_name": "主线首分歧",
                    "description": "主线板块首次有效分歧后的修复低吸观察。",
                    "category": "辅助策略",
                    "risk_level": "high",
                    "typical_holding_days": "1-3天",
                    "sort_order": 50,
                },
            ],
        )
    if "strategy_presets" not in tables:
        op.create_table(
            "strategy_presets",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=64), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("config_json", sa.Text(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index("ix_strategy_presets_name", "strategy_presets", ["name"])
        op.create_index("ix_strategy_presets_sort_order", "strategy_presets", ["sort_order"])
        op.bulk_insert(
            sa.table(
                "strategy_presets",
                sa.column("name", sa.String),
                sa.column("description", sa.Text),
                sa.column("config_json", sa.Text),
                sa.column("sort_order", sa.Integer),
            ),
            [
                {
                    "name": "快速体检",
                    "description": "全策略最近半年快速扫描，适合日常看策略状态。",
                    "config_json": json.dumps(_preset_config("6m", "open_price"), ensure_ascii=False),
                    "sort_order": 10,
                },
                {
                    "name": "年度回顾",
                    "description": "最近 1 年全策略回测，适合复盘策略稳定性。",
                    "config_json": json.dumps(_preset_config("12m", "vwap"), ensure_ascii=False),
                    "sort_order": 20,
                },
                {
                    "name": "完整检验",
                    "description": "最近 2 年保守成交模型，适合上线前检查。",
                    "config_json": json.dumps(_preset_config("24m", "open_price"), ensure_ascii=False),
                    "sort_order": 30,
                },
            ],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "strategy_presets" in tables:
        op.drop_index("ix_strategy_presets_sort_order", table_name="strategy_presets")
        op.drop_index("ix_strategy_presets_name", table_name="strategy_presets")
        op.drop_table("strategy_presets")
    if "strategy_metadata" in tables:
        op.drop_index("ix_strategy_metadata_sort_order", table_name="strategy_metadata")
        op.drop_table("strategy_metadata")


def _preset_config(range_value: str, execution_model: str) -> dict[str, object]:
    return {
        "range": range_value,
        "initial_capital": 500000,
        "strategies": [
            "first_board",
            "volume_shrink",
            "late_session_strong_support",
            "core_midcap_vwap_ma5_retrace",
            "sector_mainline_first_divergence_low_buy",
        ],
        "execution_model": execution_model,
        "max_position_pct": 30,
        "max_single_order_pct": 15,
        "max_positions": 8,
        "max_daily_loss_pct": 5,
        "min_cash_reserve": 5000,
        "stop_loss_pct": -5,
        "take_profit_pct": 10,
        "benchmark": "000300",
    }
