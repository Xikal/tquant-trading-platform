"""add high roi decision context snapshots

Revision ID: 20260530_0002
Revises: 20260530_0001
Create Date: 2026-05-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260530_0002"
down_revision = "20260530_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "decision_context_snapshots" not in tables:
        op.create_table(
            "decision_context_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("trade_date", sa.Date(), nullable=False),
            sa.Column("strategy_key", sa.String(80), nullable=False),
            sa.Column("symbol", sa.String(16), nullable=False),
            sa.Column("strategy_tier", sa.String(20), nullable=False, server_default="research"),
            sa.Column("production_eligible", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("final_decision", sa.String(24), nullable=False, server_default="watch"),
            sa.Column("final_score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("data_quality", sa.String(24), nullable=False, server_default="missing"),
            sa.Column("gates_json", sa.Text(), nullable=False),
            sa.Column("evidence_json", sa.Text(), nullable=False),
            sa.Column("source_snapshot_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("trade_date", "strategy_key", "symbol", name="uq_decision_context_day_strategy_symbol"),
        )
    inspector = sa.inspect(bind)
    _create_index_if_missing(inspector, "decision_context_snapshots", "ix_decision_context_trade_strategy_symbol", ["trade_date", "strategy_key", "symbol"])
    _create_index_if_missing(inspector, "decision_context_snapshots", "ix_decision_context_decision_quality", ["final_decision", "data_quality"])

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "signal_outcome_attributions" not in tables:
        op.create_table(
            "signal_outcome_attributions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("context_snapshot_id", sa.Integer(), sa.ForeignKey("decision_context_snapshots.id"), nullable=False),
            sa.Column("horizon_days", sa.Integer(), nullable=False),
            sa.Column("return_pct", sa.Float(), nullable=False, server_default="0"),
            sa.Column("max_gain_pct", sa.Float(), nullable=False, server_default="0"),
            sa.Column("max_drawdown_pct", sa.Float(), nullable=False, server_default="0"),
            sa.Column("hit", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("exit_reason", sa.String(120), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("context_snapshot_id", "horizon_days", name="uq_signal_outcome_context_horizon"),
        )
    inspector = sa.inspect(bind)
    _create_index_if_missing(inspector, "signal_outcome_attributions", "ix_signal_outcome_context", ["context_snapshot_id"])

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "strategy_promotion_reviews" not in tables:
        op.create_table(
            "strategy_promotion_reviews",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("strategy_key", sa.String(80), nullable=False),
            sa.Column("review_date", sa.Date(), nullable=False),
            sa.Column("window_days", sa.Integer(), nullable=False),
            sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("profit_factor", sa.Float(), nullable=False, server_default="0"),
            sa.Column("average_trade_pct", sa.Float(), nullable=False, server_default="0"),
            sa.Column("max_drawdown_pct", sa.Float(), nullable=False, server_default="0"),
            sa.Column("max5_return_pct", sa.Float(), nullable=False, server_default="0"),
            sa.Column("max10_return_pct", sa.Float(), nullable=False, server_default="0"),
            sa.Column("quarterly_stability", sa.Float(), nullable=False, server_default="0"),
            sa.Column("walk_forward_pass", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("oos_pass", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("recommendation", sa.String(32), nullable=False, server_default="stay_research"),
            sa.Column("evidence_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("strategy_key", "review_date", "window_days", name="uq_strategy_promotion_review_window"),
        )
    inspector = sa.inspect(bind)
    _create_index_if_missing(inspector, "strategy_promotion_reviews", "ix_strategy_promotion_reviews_key_date", ["strategy_key", "review_date"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "strategy_promotion_reviews" in tables:
        _drop_index_if_exists(inspector, "strategy_promotion_reviews", "ix_strategy_promotion_reviews_key_date")
        op.drop_table("strategy_promotion_reviews")
    inspector = sa.inspect(bind)
    if "signal_outcome_attributions" in set(inspector.get_table_names()):
        _drop_index_if_exists(inspector, "signal_outcome_attributions", "ix_signal_outcome_context")
        op.drop_table("signal_outcome_attributions")
    inspector = sa.inspect(bind)
    if "decision_context_snapshots" in set(inspector.get_table_names()):
        _drop_index_if_exists(inspector, "decision_context_snapshots", "ix_decision_context_decision_quality")
        _drop_index_if_exists(inspector, "decision_context_snapshots", "ix_decision_context_trade_strategy_symbol")
        op.drop_table("decision_context_snapshots")


def _create_index_if_missing(inspector, table_name: str, index_name: str, columns: list[str]) -> None:  # noqa: ANN001
    if table_name not in set(inspector.get_table_names()):
        return
    index_names = {item["name"] for item in inspector.get_indexes(table_name)}
    if index_name not in index_names:
        op.create_index(index_name, table_name, columns)


def _drop_index_if_exists(inspector, table_name: str, index_name: str) -> None:  # noqa: ANN001
    index_names = {item["name"] for item in inspector.get_indexes(table_name)}
    if index_name in index_names:
        op.drop_index(index_name, table_name=table_name)
