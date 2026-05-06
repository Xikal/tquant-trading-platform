"""phase4 phase5 foundation tables

Revision ID: 20260506_0003
Revises: 20260506_0002
Create Date: 2026-05-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260506_0003"
down_revision = "20260506_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "runtime_tasks" not in tables:
        op.create_table(
            "runtime_tasks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("task_type", sa.String(length=80), nullable=False),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="queued"),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("idempotency_key", sa.String(length=160), nullable=False, server_default=""),
            sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("result_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("progress_pct", sa.Float(), nullable=False, server_default="0"),
            sa.Column("locked_by", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("locked_at", sa.DateTime(), nullable=True),
            sa.Column("run_after", sa.DateTime(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        )
        _index("runtime_tasks", "ix_runtime_tasks_status_priority", ["status", "priority", "id"])
        _index("runtime_tasks", "ix_runtime_tasks_type_status", ["task_type", "status"])
        _index("runtime_tasks", "ix_runtime_tasks_idempotency", ["idempotency_key"])

    if "runtime_task_events" not in tables:
        op.create_table(
            "runtime_task_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(length=40), nullable=False, server_default="progress"),
            sa.Column("message", sa.String(length=240), nullable=False, server_default=""),
            sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        )
        _index("runtime_task_events", "ix_runtime_task_events_task_id", ["task_id", "id"])

    if "agent_result_quality" not in tables:
        op.create_table(
            "agent_result_quality",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("trace_id", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("provider", sa.String(length=40), nullable=False, server_default=""),
            sa.Column("agent_id", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("issue_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("issues_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("input_summary", sa.Text(), nullable=False, server_default=""),
            sa.Column("output_summary", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        )
        _index("agent_result_quality", "ix_agent_result_quality_trace", ["trace_id"])
        _index("agent_result_quality", "ix_agent_result_quality_provider_score", ["provider", "score"])

    if "quant_parameter_sets" not in tables:
        op.create_table(
            "quant_parameter_sets",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("version", sa.String(length=80), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
            sa.Column("scope", sa.String(length=40), nullable=False, server_default="low_buy"),
            sa.Column("params_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_by", sa.String(length=80), nullable=False, server_default="system"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.Column("activated_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("version", name="uq_quant_parameter_sets_version"),
        )
        _index("quant_parameter_sets", "ix_quant_parameter_sets_scope_status", ["scope", "status"])

    if "ml_signal_samples" not in tables:
        op.create_table(
            "ml_signal_samples",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("sample_key", sa.String(length=160), nullable=False),
            sa.Column("symbol", sa.String(length=16), nullable=False, server_default=""),
            sa.Column("trade_date", sa.String(length=16), nullable=False, server_default=""),
            sa.Column("strategy_key", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("feature_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("label_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("source", sa.String(length=40), nullable=False, server_default="paper"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.UniqueConstraint("sample_key", name="uq_ml_signal_samples_key"),
        )
        _index("ml_signal_samples", "ix_ml_signal_samples_symbol_date", ["symbol", "trade_date"])
        _index("ml_signal_samples", "ix_ml_signal_samples_strategy", ["strategy_key"])

    if "ml_signal_models" not in tables:
        op.create_table(
            "ml_signal_models",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("model_key", sa.String(length=120), nullable=False),
            sa.Column("model_type", sa.String(length=40), nullable=False, server_default="heuristic"),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="research"),
            sa.Column("feature_schema_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("metrics_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("artifact_uri", sa.String(length=300), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.UniqueConstraint("model_key", name="uq_ml_signal_models_key"),
        )
        _index("ml_signal_models", "ix_ml_signal_models_status", ["status"])

    if "paper_backtest_comparisons" not in tables:
        op.create_table(
            "paper_backtest_comparisons",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("account_id", sa.Integer(), nullable=False),
            sa.Column("backtest_run_id", sa.Integer(), nullable=False),
            sa.Column("comparison_date", sa.Date(), nullable=False),
            sa.Column("expected_return_pct", sa.Float(), nullable=False, server_default="0"),
            sa.Column("actual_return_pct", sa.Float(), nullable=False, server_default="0"),
            sa.Column("deviation_pct", sa.Float(), nullable=False, server_default="0"),
            sa.Column("alert", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("reason", sa.String(length=240), nullable=False, server_default=""),
            sa.Column("detail_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.UniqueConstraint("account_id", "backtest_run_id", "comparison_date", name="uq_paper_backtest_compare"),
        )
        _index("paper_backtest_comparisons", "ix_paper_backtest_compare_alert", ["alert", "comparison_date"])


def downgrade() -> None:
    for table_name in (
        "paper_backtest_comparisons",
        "ml_signal_models",
        "ml_signal_samples",
        "quant_parameter_sets",
        "agent_result_quality",
        "runtime_task_events",
        "runtime_tasks",
    ):
        op.drop_table(table_name)


def _index(table_name: str, index_name: str, columns: list[str]) -> None:
    op.create_index(index_name, table_name, columns)
