"""add active runtime task idempotency key

Revision ID: 20260508_0004
Revises: 20260508_0003
Create Date: 2026-05-08 12:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260508_0004"
down_revision = "20260508_0003"
branch_labels = None
depends_on = None

TERMINAL_STATUSES = ("succeeded", "failed", "cancelled")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("runtime_tasks")}
    if "active_idempotency_key" not in columns:
        op.add_column("runtime_tasks", sa.Column("active_idempotency_key", sa.String(length=160), nullable=True))

    _backfill_active_idempotency_keys(bind)

    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("runtime_tasks")}
    unique_constraints = {constraint["name"] for constraint in inspector.get_unique_constraints("runtime_tasks")}
    if "uq_runtime_tasks_active_idempotency" not in indexes and "uq_runtime_tasks_active_idempotency" not in unique_constraints:
        op.create_index(
            "uq_runtime_tasks_active_idempotency",
            "runtime_tasks",
            ["active_idempotency_key"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    unique_constraints = {constraint["name"] for constraint in inspector.get_unique_constraints("runtime_tasks")}
    indexes = {index["name"] for index in inspector.get_indexes("runtime_tasks")}
    if "uq_runtime_tasks_active_idempotency" in unique_constraints:
        op.drop_constraint("uq_runtime_tasks_active_idempotency", "runtime_tasks", type_="unique")
    elif "uq_runtime_tasks_active_idempotency" in indexes:
        op.drop_index("uq_runtime_tasks_active_idempotency", table_name="runtime_tasks")
    columns = {column["name"] for column in inspector.get_columns("runtime_tasks")}
    if "active_idempotency_key" in columns:
        op.drop_column("runtime_tasks", "active_idempotency_key")


def _backfill_active_idempotency_keys(bind) -> None:
    rows = bind.execute(
        sa.text(
            """
            SELECT id, idempotency_key, status
            FROM runtime_tasks
            WHERE idempotency_key <> ''
            ORDER BY id ASC
            """
        )
    ).mappings().all()
    seen: set[str] = set()
    for row in rows:
        key = str(row["idempotency_key"] or "")
        status = str(row["status"] or "")
        active_key = key if key and status not in TERMINAL_STATUSES and key not in seen else None
        if active_key:
            seen.add(key)
        bind.execute(
            sa.text("UPDATE runtime_tasks SET active_idempotency_key = :active_key WHERE id = :id"),
            {"active_key": active_key, "id": row["id"]},
        )
