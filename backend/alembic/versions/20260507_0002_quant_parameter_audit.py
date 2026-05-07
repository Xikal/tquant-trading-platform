"""add quant parameter audit log

Revision ID: 20260507_0002
Revises: 20260507_0001
Create Date: 2026-05-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260507_0002"
down_revision = "20260507_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "quant_parameter_audit_log" not in tables:
        op.create_table(
            "quant_parameter_audit_log",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("action", sa.String(length=40), nullable=False, server_default=""),
            sa.Column("version", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("scope", sa.String(length=40), nullable=False, server_default="global"),
            sa.Column("operator", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("before_json", sa.Text(), nullable=False),
            sa.Column("after_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        )
        op.create_index("ix_quant_parameter_audit_action", "quant_parameter_audit_log", ["action"])
        op.create_index("ix_quant_parameter_audit_version", "quant_parameter_audit_log", ["version"])
        op.create_index("ix_quant_parameter_audit_scope", "quant_parameter_audit_log", ["scope"])
        op.create_index("ix_quant_parameter_audit_created", "quant_parameter_audit_log", ["created_at"])
    if "ml_signal_models" in tables:
        columns = {item["name"] for item in inspector.get_columns("ml_signal_models")}
        if "remote_artifact_uri" not in columns:
            op.add_column("ml_signal_models", sa.Column("remote_artifact_uri", sa.String(length=500), nullable=False, server_default=""))
        if "artifact_checksum" not in columns:
            op.add_column("ml_signal_models", sa.Column("artifact_checksum", sa.String(length=128), nullable=False, server_default=""))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "quant_parameter_audit_log" in tables:
        for index_name in (
            "ix_quant_parameter_audit_created",
            "ix_quant_parameter_audit_scope",
            "ix_quant_parameter_audit_version",
            "ix_quant_parameter_audit_action",
        ):
            if index_name in {item["name"] for item in inspector.get_indexes("quant_parameter_audit_log")}:
                op.drop_index(index_name, table_name="quant_parameter_audit_log")
        op.drop_table("quant_parameter_audit_log")
    if "ml_signal_models" in tables:
        columns = {item["name"] for item in inspector.get_columns("ml_signal_models")}
        if "artifact_checksum" in columns:
            op.drop_column("ml_signal_models", "artifact_checksum")
        if "remote_artifact_uri" in columns:
            op.drop_column("ml_signal_models", "remote_artifact_uri")
