"""Add trading experience observation tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260602_0001"
down_revision = "20260601_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trading_experience_review_pool_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pool_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="in_pool"),
        sa.Column("entry_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("volume_ratio", sa.Float(), nullable=False, server_default="0"),
        sa.Column("mainline_state", sa.String(length=48), nullable=False, server_default="unknown"),
        sa.Column("sector_role", sa.String(length=48), nullable=False, server_default="unknown"),
        sa.Column("drop_reason", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("tracked_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("data_quality", sa.String(length=24), nullable=False, server_default="insufficient"),
        sa.Column("as_of", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("engine_version", sa.String(length=40), nullable=False, server_default="trading-experience-v1"),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("pool_date", "symbol", name="uq_trading_experience_review_pool_day_symbol"),
    )
    op.create_index("ix_trading_experience_review_pool_items_pool_date", "trading_experience_review_pool_items", ["pool_date"])
    op.create_index("ix_trading_experience_review_pool_items_symbol", "trading_experience_review_pool_items", ["symbol"])
    op.create_index("ix_trading_experience_review_pool_items_status", "trading_experience_review_pool_items", ["status"])
    op.create_index("ix_trading_experience_review_pool_items_data_quality", "trading_experience_review_pool_items", ["data_quality"])
    op.create_index("ix_trading_experience_review_pool_items_as_of", "trading_experience_review_pool_items", ["as_of"])
    op.create_index("ix_trading_experience_review_pool_items_engine_version", "trading_experience_review_pool_items", ["engine_version"])

    op.create_table(
        "trading_experience_trade_journal_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("paper_accounts.id"), nullable=True),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("reason_text", sa.Text(), nullable=False),
        sa.Column("signal_source", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("discipline_flags_json", sa.Text(), nullable=False),
        sa.Column("mistake_tags_json", sa.Text(), nullable=False),
        sa.Column("data_quality", sa.String(length=24), nullable=False, server_default="ok"),
        sa.Column("engine_version", sa.String(length=40), nullable=False, server_default="trading-experience-v1"),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_trading_experience_trade_journal_entries_user_id", "trading_experience_trade_journal_entries", ["user_id"])
    op.create_index("ix_trading_experience_trade_journal_entries_account_id", "trading_experience_trade_journal_entries", ["account_id"])
    op.create_index("ix_trading_experience_trade_journal_entries_symbol", "trading_experience_trade_journal_entries", ["symbol"])
    op.create_index("ix_trading_experience_trade_journal_entries_action", "trading_experience_trade_journal_entries", ["action"])
    op.create_index("ix_trading_experience_trade_journal_entries_data_quality", "trading_experience_trade_journal_entries", ["data_quality"])
    op.create_index("ix_trading_experience_trade_journal_entries_created_at", "trading_experience_trade_journal_entries", ["created_at"])

    op.create_table(
        "trading_experience_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("snapshot_type", sa.String(length=64), nullable=False),
        sa.Column("snapshot_key", sa.String(length=120), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("data_quality", sa.String(length=24), nullable=False, server_default="insufficient"),
        sa.Column("as_of", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("engine_version", sa.String(length=40), nullable=False, server_default="trading-experience-v1"),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "snapshot_type",
            "snapshot_key",
            "trade_date",
            "engine_version",
            name="uq_trading_experience_snapshot_type_key_day_version",
        ),
    )
    op.create_index("ix_trading_experience_snapshots_snapshot_type", "trading_experience_snapshots", ["snapshot_type"])
    op.create_index("ix_trading_experience_snapshots_snapshot_key", "trading_experience_snapshots", ["snapshot_key"])
    op.create_index("ix_trading_experience_snapshots_trade_date", "trading_experience_snapshots", ["trade_date"])
    op.create_index("ix_trading_experience_snapshots_data_quality", "trading_experience_snapshots", ["data_quality"])
    op.create_index("ix_trading_experience_snapshots_as_of", "trading_experience_snapshots", ["as_of"])
    op.create_index("ix_trading_experience_snapshots_engine_version", "trading_experience_snapshots", ["engine_version"])


def downgrade() -> None:
    op.drop_table("trading_experience_snapshots")
    op.drop_table("trading_experience_trade_journal_entries")
    op.drop_table("trading_experience_review_pool_items")
