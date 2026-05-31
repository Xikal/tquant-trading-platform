"""add data quality sla snapshots

Revision ID: 20260531_0001
Revises: 20260530_0002
Create Date: 2026-05-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260531_0001"
down_revision = "20260530_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "data_quality_snapshots" not in tables:
        op.create_table(
            "data_quality_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("dataset_key", sa.String(64), nullable=False),
            sa.Column("as_of_date", sa.Date(), nullable=False),
            sa.Column("scope", sa.String(40), nullable=False),
            sa.Column("expected_days", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("actual_days", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("missing_days", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("invalid_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("duplicate_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("stale", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("coverage_pct", sa.Float(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(24), nullable=False, server_default="unknown"),
            sa.Column("blockers_json", sa.Text(), nullable=False),
            sa.Column("checked_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("dataset_key", "as_of_date", "scope", name="uq_data_quality_snapshot_dataset_scope_day"),
        )
    inspector = sa.inspect(bind)
    _create_index_if_missing(inspector, "data_quality_snapshots", "ix_data_quality_snapshots_dataset_key", ["dataset_key"])
    _create_index_if_missing(inspector, "data_quality_snapshots", "ix_data_quality_snapshots_as_of_date", ["as_of_date"])
    _create_index_if_missing(inspector, "data_quality_snapshots", "ix_data_quality_snapshots_scope", ["scope"])
    _create_index_if_missing(inspector, "data_quality_snapshots", "ix_data_quality_snapshots_stale", ["stale"])
    _create_index_if_missing(inspector, "data_quality_snapshots", "ix_data_quality_snapshots_status", ["status"])
    _create_index_if_missing(inspector, "data_quality_snapshots", "ix_data_quality_snapshots_checked_at", ["checked_at"])

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "data_repair_audits" not in tables:
        op.create_table(
            "data_repair_audits",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("repair_id", sa.String(80), nullable=False),
            sa.Column("dataset_key", sa.String(64), nullable=False),
            sa.Column("reason", sa.String(120), nullable=False),
            sa.Column("detected_rows_json", sa.Text(), nullable=False),
            sa.Column("backup_path", sa.Text(), nullable=False),
            sa.Column("refetch_result", sa.Text(), nullable=False),
            sa.Column("deleted_rows_json", sa.Text(), nullable=False),
            sa.Column("fabricated", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("operator", sa.String(80), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("repair_id", name="uq_data_repair_audit_repair_id"),
        )
    inspector = sa.inspect(bind)
    _create_index_if_missing(inspector, "data_repair_audits", "ix_data_repair_audits_repair_id", ["repair_id"])
    _create_index_if_missing(inspector, "data_repair_audits", "ix_data_repair_audits_dataset_key", ["dataset_key"])
    _create_index_if_missing(inspector, "data_repair_audits", "ix_data_repair_audits_reason", ["reason"])
    _create_index_if_missing(inspector, "data_repair_audits", "ix_data_repair_audits_fabricated", ["fabricated"])
    _create_index_if_missing(inspector, "data_repair_audits", "ix_data_repair_audits_created_at", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "data_repair_audits" in tables:
        _drop_index_if_exists(inspector, "data_repair_audits", "ix_data_repair_audits_created_at")
        _drop_index_if_exists(inspector, "data_repair_audits", "ix_data_repair_audits_fabricated")
        _drop_index_if_exists(inspector, "data_repair_audits", "ix_data_repair_audits_reason")
        _drop_index_if_exists(inspector, "data_repair_audits", "ix_data_repair_audits_dataset_key")
        _drop_index_if_exists(inspector, "data_repair_audits", "ix_data_repair_audits_repair_id")
        op.drop_table("data_repair_audits")
    inspector = sa.inspect(bind)
    if "data_quality_snapshots" in set(inspector.get_table_names()):
        _drop_index_if_exists(inspector, "data_quality_snapshots", "ix_data_quality_snapshots_checked_at")
        _drop_index_if_exists(inspector, "data_quality_snapshots", "ix_data_quality_snapshots_status")
        _drop_index_if_exists(inspector, "data_quality_snapshots", "ix_data_quality_snapshots_stale")
        _drop_index_if_exists(inspector, "data_quality_snapshots", "ix_data_quality_snapshots_scope")
        _drop_index_if_exists(inspector, "data_quality_snapshots", "ix_data_quality_snapshots_as_of_date")
        _drop_index_if_exists(inspector, "data_quality_snapshots", "ix_data_quality_snapshots_dataset_key")
        op.drop_table("data_quality_snapshots")


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
