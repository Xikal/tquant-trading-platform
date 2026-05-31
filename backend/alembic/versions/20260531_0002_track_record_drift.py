"""add track record drift snapshots

Revision ID: 20260531_0002
Revises: 20260531_0001
Create Date: 2026-05-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260531_0002"
down_revision = "20260531_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "production_signal_ledger" not in tables:
        op.create_table(
            "production_signal_ledger",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("signal_date", sa.Date(), nullable=False),
            sa.Column("strategy_key", sa.String(80), nullable=False),
            sa.Column("symbol", sa.String(16), nullable=False),
            sa.Column("name", sa.String(64), nullable=False, server_default=""),
            sa.Column("signal_state", sa.String(24), nullable=False),
            sa.Column("production_score", sa.Float(), nullable=True),
            sa.Column("priority_score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("entry_zone_low", sa.Float(), nullable=False, server_default="0"),
            sa.Column("entry_zone_high", sa.Float(), nullable=False, server_default="0"),
            sa.Column("stop_loss", sa.Float(), nullable=False, server_default="0"),
            sa.Column("expected_horizon_returns_json", sa.Text(), nullable=False),
            sa.Column("market_regime", sa.String(40), nullable=False, server_default=""),
            sa.Column("front_row_tier", sa.String(40), nullable=False, server_default=""),
            sa.Column("data_quality", sa.String(40), nullable=False, server_default="unknown"),
            sa.Column("signal_time", sa.DateTime(), nullable=False),
            sa.Column("data_cutoff_time", sa.DateTime(), nullable=False),
            sa.Column("return_start_time", sa.DateTime(), nullable=False),
            sa.Column("source_version", sa.String(80), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("signal_date", "strategy_key", "symbol", name="uq_production_signal_ledger_signal"),
        )
    inspector = sa.inspect(bind)
    _create_index_if_missing(inspector, "production_signal_ledger", "ix_production_signal_ledger_signal_date", ["signal_date"])
    _create_index_if_missing(inspector, "production_signal_ledger", "ix_production_signal_ledger_strategy_key", ["strategy_key"])
    _create_index_if_missing(inspector, "production_signal_ledger", "ix_production_signal_ledger_symbol", ["symbol"])
    _create_index_if_missing(inspector, "production_signal_ledger", "ix_production_signal_ledger_signal_state", ["signal_state"])
    _create_index_if_missing(inspector, "production_signal_ledger", "ix_production_signal_ledger_market_regime", ["market_regime"])
    _create_index_if_missing(inspector, "production_signal_ledger", "ix_production_signal_ledger_front_row_tier", ["front_row_tier"])
    _create_index_if_missing(inspector, "production_signal_ledger", "ix_production_signal_ledger_data_quality", ["data_quality"])
    _create_index_if_missing(inspector, "production_signal_ledger", "ix_production_signal_ledger_signal_time", ["signal_time"])
    _create_index_if_missing(inspector, "production_signal_ledger", "ix_production_signal_ledger_data_cutoff_time", ["data_cutoff_time"])
    _create_index_if_missing(inspector, "production_signal_ledger", "ix_production_signal_ledger_return_start_time", ["return_start_time"])
    _create_index_if_missing(inspector, "production_signal_ledger", "ix_production_signal_ledger_created_at", ["created_at"])

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "signal_realized_outcomes" not in tables:
        op.create_table(
            "signal_realized_outcomes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("ledger_id", sa.Integer(), sa.ForeignKey("production_signal_ledger.id"), nullable=False),
            sa.Column("horizon_days", sa.Integer(), nullable=False),
            sa.Column("return_pct", sa.Float(), nullable=True),
            sa.Column("max_gain_pct", sa.Float(), nullable=True),
            sa.Column("max_drawdown_pct", sa.Float(), nullable=True),
            sa.Column("exit_reason", sa.String(80), nullable=False, server_default=""),
            sa.Column("return_start_time", sa.DateTime(), nullable=False),
            sa.Column("settled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("data_quality", sa.String(40), nullable=False, server_default="unknown"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("ledger_id", "horizon_days", name="uq_signal_realized_outcome_ledger_horizon"),
        )
    inspector = sa.inspect(bind)
    _create_index_if_missing(inspector, "signal_realized_outcomes", "ix_signal_realized_outcomes_ledger_id", ["ledger_id"])
    _create_index_if_missing(inspector, "signal_realized_outcomes", "ix_signal_realized_outcomes_horizon_days", ["horizon_days"])
    _create_index_if_missing(inspector, "signal_realized_outcomes", "ix_signal_realized_outcomes_return_start_time", ["return_start_time"])
    _create_index_if_missing(inspector, "signal_realized_outcomes", "ix_signal_realized_outcomes_settled", ["settled"])
    _create_index_if_missing(inspector, "signal_realized_outcomes", "ix_signal_realized_outcomes_data_quality", ["data_quality"])
    _create_index_if_missing(inspector, "signal_realized_outcomes", "ix_signal_realized_outcomes_created_at", ["created_at"])

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "strategy_drift_snapshots" not in tables:
        op.create_table(
            "strategy_drift_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("strategy_key", sa.String(80), nullable=False),
            sa.Column("as_of_date", sa.Date(), nullable=False),
            sa.Column("window_days", sa.Integer(), nullable=False),
            sa.Column("realized_pf", sa.Float(), nullable=True),
            sa.Column("expected_pf", sa.Float(), nullable=True),
            sa.Column("realized_avg", sa.Float(), nullable=False, server_default="0"),
            sa.Column("expected_avg", sa.Float(), nullable=False, server_default="0"),
            sa.Column("realized_winrate", sa.Float(), nullable=False, server_default="0"),
            sa.Column("expected_winrate", sa.Float(), nullable=False, server_default="0"),
            sa.Column("realized_max5", sa.Float(), nullable=False, server_default="0"),
            sa.Column("backtest_max5", sa.Float(), nullable=False, server_default="0"),
            sa.Column("realized_max10", sa.Float(), nullable=False, server_default="0"),
            sa.Column("backtest_max10", sa.Float(), nullable=False, server_default="0"),
            sa.Column("tracking_error", sa.Float(), nullable=False, server_default="0"),
            sa.Column("decay_pct", sa.Float(), nullable=False, server_default="0"),
            sa.Column("drift_flag", sa.String(40), nullable=False, server_default="insufficient_sample"),
            sa.Column("sample_settled", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("strategy_key", "as_of_date", "window_days", name="uq_strategy_drift_snapshot_key_window"),
        )
    inspector = sa.inspect(bind)
    _create_index_if_missing(inspector, "strategy_drift_snapshots", "ix_strategy_drift_snapshots_strategy_key", ["strategy_key"])
    _create_index_if_missing(inspector, "strategy_drift_snapshots", "ix_strategy_drift_snapshots_as_of_date", ["as_of_date"])
    _create_index_if_missing(inspector, "strategy_drift_snapshots", "ix_strategy_drift_snapshots_window_days", ["window_days"])
    _create_index_if_missing(inspector, "strategy_drift_snapshots", "ix_strategy_drift_snapshots_drift_flag", ["drift_flag"])
    _create_index_if_missing(inspector, "strategy_drift_snapshots", "ix_strategy_drift_snapshots_created_at", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "strategy_drift_snapshots" in set(inspector.get_table_names()):
        _drop_index_if_exists(inspector, "strategy_drift_snapshots", "ix_strategy_drift_snapshots_created_at")
        _drop_index_if_exists(inspector, "strategy_drift_snapshots", "ix_strategy_drift_snapshots_drift_flag")
        _drop_index_if_exists(inspector, "strategy_drift_snapshots", "ix_strategy_drift_snapshots_window_days")
        _drop_index_if_exists(inspector, "strategy_drift_snapshots", "ix_strategy_drift_snapshots_as_of_date")
        _drop_index_if_exists(inspector, "strategy_drift_snapshots", "ix_strategy_drift_snapshots_strategy_key")
        op.drop_table("strategy_drift_snapshots")
    inspector = sa.inspect(bind)
    if "signal_realized_outcomes" in set(inspector.get_table_names()):
        _drop_index_if_exists(inspector, "signal_realized_outcomes", "ix_signal_realized_outcomes_created_at")
        _drop_index_if_exists(inspector, "signal_realized_outcomes", "ix_signal_realized_outcomes_data_quality")
        _drop_index_if_exists(inspector, "signal_realized_outcomes", "ix_signal_realized_outcomes_settled")
        _drop_index_if_exists(inspector, "signal_realized_outcomes", "ix_signal_realized_outcomes_return_start_time")
        _drop_index_if_exists(inspector, "signal_realized_outcomes", "ix_signal_realized_outcomes_horizon_days")
        _drop_index_if_exists(inspector, "signal_realized_outcomes", "ix_signal_realized_outcomes_ledger_id")
        op.drop_table("signal_realized_outcomes")
    inspector = sa.inspect(bind)
    if "production_signal_ledger" in set(inspector.get_table_names()):
        _drop_index_if_exists(inspector, "production_signal_ledger", "ix_production_signal_ledger_created_at")
        _drop_index_if_exists(inspector, "production_signal_ledger", "ix_production_signal_ledger_return_start_time")
        _drop_index_if_exists(inspector, "production_signal_ledger", "ix_production_signal_ledger_data_cutoff_time")
        _drop_index_if_exists(inspector, "production_signal_ledger", "ix_production_signal_ledger_signal_time")
        _drop_index_if_exists(inspector, "production_signal_ledger", "ix_production_signal_ledger_data_quality")
        _drop_index_if_exists(inspector, "production_signal_ledger", "ix_production_signal_ledger_front_row_tier")
        _drop_index_if_exists(inspector, "production_signal_ledger", "ix_production_signal_ledger_market_regime")
        _drop_index_if_exists(inspector, "production_signal_ledger", "ix_production_signal_ledger_signal_state")
        _drop_index_if_exists(inspector, "production_signal_ledger", "ix_production_signal_ledger_symbol")
        _drop_index_if_exists(inspector, "production_signal_ledger", "ix_production_signal_ledger_strategy_key")
        _drop_index_if_exists(inspector, "production_signal_ledger", "ix_production_signal_ledger_signal_date")
        op.drop_table("production_signal_ledger")


def _create_index_if_missing(inspector, table_name: str, index_name: str, columns: list[str]) -> None:  # noqa: ANN001
    if table_name not in set(inspector.get_table_names()):
        return
    index_names = {item["name"] for item in inspector.get_indexes(table_name)}
    if index_name not in index_names:
        op.create_index(index_name, table_name, columns)


def _drop_index_if_exists(inspector, table_name: str, index_name: str) -> None:  # noqa: ANN001
    if table_name not in set(inspector.get_table_names()):
        return
    index_names = {item["name"] for item in inspector.get_indexes(table_name)}
    if index_name in index_names:
        op.drop_index(index_name, table_name=table_name)
