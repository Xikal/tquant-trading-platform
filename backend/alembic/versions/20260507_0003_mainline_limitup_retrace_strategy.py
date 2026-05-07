"""add mainline limitup retrace strategy metadata

Revision ID: 20260507_0003
Revises: 20260507_0002
Create Date: 2026-05-07
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op


revision = "20260507_0003"
down_revision = "20260507_0002"
branch_labels = None
depends_on = None


STRATEGY_KEY = "mainline_limitup_shrink_retrace_reclaim"
PREVIOUS_PRODUCTION_KEYS = {
    "first_board",
    "volume_shrink",
    "late_session_strong_support",
    "core_midcap_vwap_ma5_retrace",
    "sector_mainline_first_divergence_low_buy",
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "strategy_metadata" in tables:
        existing = bind.execute(
            sa.text("SELECT `key` FROM strategy_metadata WHERE `key` = :key"),
            {"key": STRATEGY_KEY},
        ).first()
        if existing is None:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO strategy_metadata
                        (`key`, display_name, description, category, risk_level,
                         typical_holding_days, sort_order, enabled, probe_status,
                         probe_summary, visibility)
                    VALUES
                        (:key, :display_name, :description, :category, :risk_level,
                         :typical_holding_days, :sort_order, :enabled, :probe_status,
                         :probe_summary, :visibility)
                    """
                ),
                {
                    "key": STRATEGY_KEY,
                    "display_name": "主线涨停回调",
                    "description": "主线板块涨停启动后，等待缩量回调到均线合一区或双底支撑，并重新站回 5 日线。",
                    "category": "auxiliary",
                    "risk_level": "medium",
                    "typical_holding_days": "2-5天",
                    "sort_order": 60,
                    "enabled": True,
                    "probe_status": "not_required",
                    "probe_summary": "",
                    "visibility": "full",
                },
            )
    if "strategy_presets" in tables:
        _append_strategy_to_default_presets(bind)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "strategy_presets" in tables:
        _remove_strategy_from_presets(bind)
    if "strategy_metadata" in tables:
        bind.execute(sa.text("DELETE FROM strategy_metadata WHERE `key` = :key"), {"key": STRATEGY_KEY})


def _append_strategy_to_default_presets(bind) -> None:
    rows = bind.execute(sa.text("SELECT id, config_json FROM strategy_presets")).all()
    for row in rows:
        config = _loads_config(row.config_json)
        strategies = config.get("strategies")
        if not isinstance(strategies, list):
            continue
        normalized = [str(item) for item in strategies]
        if STRATEGY_KEY in normalized:
            continue
        if not PREVIOUS_PRODUCTION_KEYS.issubset(set(normalized)):
            continue
        config["strategies"] = [*normalized, STRATEGY_KEY]
        bind.execute(
            sa.text("UPDATE strategy_presets SET config_json = :config_json WHERE id = :id"),
            {"id": row.id, "config_json": json.dumps(config, ensure_ascii=False)},
        )


def _remove_strategy_from_presets(bind) -> None:
    rows = bind.execute(sa.text("SELECT id, config_json FROM strategy_presets")).all()
    for row in rows:
        config = _loads_config(row.config_json)
        strategies = config.get("strategies")
        if not isinstance(strategies, list):
            continue
        next_strategies = [str(item) for item in strategies if str(item) != STRATEGY_KEY]
        if next_strategies == strategies:
            continue
        config["strategies"] = next_strategies
        bind.execute(
            sa.text("UPDATE strategy_presets SET config_json = :config_json WHERE id = :id"),
            {"id": row.id, "config_json": json.dumps(config, ensure_ascii=False)},
        )


def _loads_config(raw: str | None) -> dict[str, object]:
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}
