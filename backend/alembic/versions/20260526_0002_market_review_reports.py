"""add market review reports

Revision ID: 20260526_0002
Revises: 20260526_0001
Create Date: 2026-05-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260526_0002"
down_revision = "20260526_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "market_review_reports" in set(inspector.get_table_names()):
        return
    op.create_table(
        "market_review_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("report_slot", sa.String(length=16), nullable=False, server_default="close"),
        sa.Column("overall_summary", sa.Text(), nullable=False),
        sa.Column("strategy_highlights", sa.Text(), nullable=False),
        sa.Column("risk_alerts", sa.Text(), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=False),
        sa.Column("raw_metrics_snapshot", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("llm_model", sa.String(length=80), nullable=False, server_default="market-rule"),
        sa.UniqueConstraint("report_date", "report_slot", name="uq_market_review_date_slot"),
    )
    op.create_index("ix_market_review_reports_report_date", "market_review_reports", ["report_date"])
    op.create_index("ix_market_review_reports_report_slot", "market_review_reports", ["report_slot"])
    op.create_index("ix_market_review_reports_generated_at", "market_review_reports", ["generated_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "market_review_reports" not in set(inspector.get_table_names()):
        return
    for index_name in (
        "ix_market_review_reports_generated_at",
        "ix_market_review_reports_report_slot",
        "ix_market_review_reports_report_date",
    ):
        if index_name in {index["name"] for index in inspector.get_indexes("market_review_reports")}:
            op.drop_index(index_name, table_name="market_review_reports")
    op.drop_table("market_review_reports")
