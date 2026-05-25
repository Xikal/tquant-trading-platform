"""add paper midday and close review reports

Revision ID: 20260525_0001
Revises: 20260524_0001
Create Date: 2026-05-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260525_0001"
down_revision = "20260524_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "paper_review_reports" in set(inspector.get_table_names()):
        return
    op.create_table(
        "paper_review_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("paper_accounts.id"), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("report_slot", sa.String(length=16), nullable=False, server_default="close"),
        sa.Column("overall_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("strategy_highlights", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("risk_alerts", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("suggestion", sa.Text(), nullable=False, server_default=""),
        sa.Column("raw_metrics_snapshot", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("generated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("llm_model", sa.String(length=80), nullable=False, server_default=""),
        sa.UniqueConstraint("account_id", "report_date", "report_slot", name="uq_prr_account_date_slot"),
    )
    op.create_index("ix_paper_review_reports_account_id", "paper_review_reports", ["account_id"])
    op.create_index("ix_paper_review_reports_report_date", "paper_review_reports", ["report_date"])
    op.create_index("ix_paper_review_reports_report_slot", "paper_review_reports", ["report_slot"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "paper_review_reports" not in set(inspector.get_table_names()):
        return
    for index_name in (
        "ix_paper_review_reports_report_slot",
        "ix_paper_review_reports_report_date",
        "ix_paper_review_reports_account_id",
    ):
        if index_name in {index["name"] for index in inspector.get_indexes("paper_review_reports")}:
            op.drop_index(index_name, table_name="paper_review_reports")
    op.drop_table("paper_review_reports")
