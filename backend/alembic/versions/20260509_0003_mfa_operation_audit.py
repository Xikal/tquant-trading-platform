"""add TOTP MFA fields and operation audit log

Revision ID: 20260509_0003
Revises: 20260509_0002
Create Date: 2026-05-09 16:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260509_0003"
down_revision = "20260509_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "mfa_totp_enabled" not in user_columns:
        op.add_column("users", sa.Column("mfa_totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "mfa_totp_secret" not in user_columns:
        op.add_column("users", sa.Column("mfa_totp_secret", sa.String(length=80), nullable=False, server_default=""))
    indexes = {index["name"] for index in inspector.get_indexes("users")}
    if "ix_users_mfa_totp_enabled" not in indexes:
        op.create_index("ix_users_mfa_totp_enabled", "users", ["mfa_totp_enabled"])
    if "operation_audit_log" not in inspector.get_table_names():
        op.create_table(
            "operation_audit_log",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("operation", sa.String(length=80), nullable=False),
            sa.Column("resource_type", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("resource_id", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="ok"),
            sa.Column("operator_ip", sa.String(length=80), nullable=False, server_default=""),
            # MySQL does not allow defaults on TEXT/JSON columns. Application
            # writes always provide a sanitized JSON string, so keep the column
            # NOT NULL without a server-side default.
            sa.Column("detail_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index("ix_operation_audit_log_user_id", "operation_audit_log", ["user_id"])
        op.create_index("ix_operation_audit_log_operation", "operation_audit_log", ["operation"])
        op.create_index("ix_operation_audit_log_resource_type", "operation_audit_log", ["resource_type"])
        op.create_index("ix_operation_audit_log_resource_id", "operation_audit_log", ["resource_id"])
        op.create_index("ix_operation_audit_log_status", "operation_audit_log", ["status"])
        op.create_index("ix_operation_audit_log_created_at", "operation_audit_log", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "operation_audit_log" in inspector.get_table_names():
        op.drop_table("operation_audit_log")
    indexes = {index["name"] for index in inspector.get_indexes("users")}
    if "ix_users_mfa_totp_enabled" in indexes:
        op.drop_index("ix_users_mfa_totp_enabled", table_name="users")
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    for column in ("mfa_totp_secret", "mfa_totp_enabled"):
        if column in user_columns:
            op.drop_column("users", column)
