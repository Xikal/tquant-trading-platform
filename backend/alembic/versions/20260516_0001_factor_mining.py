"""add factor mining tables

Revision ID: 20260516_0001
Revises: 20260513_0001
Create Date: 2026-05-16 10:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260516_0001"
down_revision = "20260513_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "factor_definitions" not in tables:
        op.create_table(
            "factor_definitions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("factor_key", sa.String(length=120), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("hypothesis", sa.Text(), nullable=False),
            sa.Column("formula_code", sa.Text(), nullable=False),
            sa.Column("data_deps_json", sa.Text(), nullable=False),
            sa.Column("direction", sa.String(length=24), nullable=False, server_default="higher_better"),
            sa.Column("category", sa.String(length=40), nullable=False, server_default="price"),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="candidate"),
            sa.Column("source", sa.String(length=40), nullable=False, server_default="human_crafted"),
            sa.Column("version", sa.String(length=40), nullable=False, server_default="v1"),
            sa.Column("eval_result_json", sa.Text(), nullable=False),
            sa.Column("created_by", sa.String(length=80), nullable=False, server_default="system"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint("factor_key", name="uq_factor_definitions_key"),
        )
        _index("factor_definitions", "ix_factor_definitions_key", ["factor_key"])
        _index("factor_definitions", "ix_factor_definitions_status", ["status"])
        _index("factor_definitions", "ix_factor_definitions_source", ["source"])
        _index("factor_definitions", "ix_factor_definitions_created_at", ["created_at"])
    if "factor_eval_runs" not in tables:
        op.create_table(
            "factor_eval_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("factor_key", sa.String(length=120), nullable=False),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="succeeded"),
            sa.Column("start_date", sa.String(length=16), nullable=False, server_default=""),
            sa.Column("end_date", sa.String(length=16), nullable=False, server_default=""),
            sa.Column("symbol_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("observation_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("metrics_json", sa.Text(), nullable=False),
            sa.Column("interpretation_json", sa.Text(), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=False),
            sa.Column("elapsed_seconds", sa.Float(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )
        _index("factor_eval_runs", "ix_factor_eval_runs_factor_key", ["factor_key"])
        _index("factor_eval_runs", "ix_factor_eval_runs_status", ["status"])
        _index("factor_eval_runs", "ix_factor_eval_runs_start_date", ["start_date"])
        _index("factor_eval_runs", "ix_factor_eval_runs_end_date", ["end_date"])
        _index("factor_eval_runs", "ix_factor_eval_runs_created_at", ["created_at"])
    if "factor_approvals" not in tables:
        op.create_table(
            "factor_approvals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("factor_key", sa.String(length=120), nullable=False),
            sa.Column("action", sa.String(length=40), nullable=False, server_default=""),
            sa.Column("from_status", sa.String(length=24), nullable=False, server_default=""),
            sa.Column("to_status", sa.String(length=24), nullable=False, server_default=""),
            sa.Column("operator_user_id", sa.Integer(), nullable=True),
            sa.Column("detail_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )
        _index("factor_approvals", "ix_factor_approvals_factor_key", ["factor_key"])
        _index("factor_approvals", "ix_factor_approvals_action", ["action"])
        _index("factor_approvals", "ix_factor_approvals_operator_user_id", ["operator_user_id"])
        _index("factor_approvals", "ix_factor_approvals_created_at", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    for table in ("factor_approvals", "factor_eval_runs", "factor_definitions"):
        if table in tables:
            op.drop_table(table)


def _index(table: str, name: str, columns: list[str]) -> None:
    op.create_index(name, table, columns)
