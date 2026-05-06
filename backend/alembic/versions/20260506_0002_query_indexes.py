"""materialize query indexes previously covered by schema compat

Revision ID: 20260506_0002
Revises: 20260506_v9_workbench
Create Date: 2026-05-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260506_0002"
down_revision = "20260506_v9_workbench"
branch_labels = None
depends_on = None


INDEX_SPECS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("instruments", "ix_instr_type_sector_symbol", ("instrument_type", "sector_name", "symbol")),
    ("daily_bar_snapshots", "ix_daily_type_date_symbol", ("instrument_type", "trade_date", "symbol")),
    ("daily_bar_snapshots", "ix_daily_date_symbol", ("trade_date", "symbol")),
    ("minute_bar_snapshots", "ix_minute_symbol_period_time", ("symbol", "bar_period", "bar_timestamp")),
    ("minute_bar_snapshots", "ix_minute_period_time", ("bar_period", "bar_timestamp")),
    ("low_buy_strategy_pool_snapshots", "ix_lb_pool_date_strategy_score", ("latest_trade_date", "strategy_key", "pool_key", "rank_score")),
    ("low_buy_strategy_pool_snapshots", "ix_lb_pool_key_date_strategy", ("pool_key", "latest_trade_date", "strategy_key")),
    ("low_buy_result_snapshots", "ix_lb_result_date_strategy_score", ("latest_trade_date", "strategy_key", "score")),
    ("low_buy_result_snapshots", "ix_lb_result_date_strategy_state", ("latest_trade_date", "strategy_key", "buy_signal_state", "score")),
    ("low_buy_result_snapshots", "ix_lb_result_strategy_symbol_date", ("strategy_key", "symbol", "latest_trade_date")),
    ("low_buy_scan_snapshots", "ix_lb_scan_strategy_date_updated", ("strategy_key", "latest_trade_date", "updated_at")),
    ("low_buy_strategy_performance_window_snapshots", "ix_lb_perf_strategy_date_window", ("strategy_key", "latest_trade_date", "lookback_days")),
    ("user_watchlists", "ix_user_watchlists_user_updated", ("user_id", "updated_at")),
    ("watchlist", "ix_watchlist_available_position_date", ("available_position_date",)),
    ("user_watchlists", "ix_user_watchlists_available_position_date", ("available_position_date",)),
    ("user_feishu_bindings", "ix_feishu_bindings_status_tenant", ("status", "tenant_key")),
    ("watchlist_signal_snapshots", "ix_watchlist_signal_updated", ("updated_at", "symbol")),
    ("low_buy_trade_lifecycle_snapshots", "ix_lb_lifecycle_scope_status_date", ("user_scope", "status", "signal_trade_date")),
    ("paper_positions", "ix_paper_positions_account_symbol", ("account_id", "symbol")),
    ("paper_orders", "ix_paper_orders_account_created", ("account_id", "created_at")),
    ("paper_trades", "ix_paper_trades_account_time", ("account_id", "trade_time")),
    ("paper_trade_tags", "ix_paper_trade_tags_account_tag", ("account_id", "tag")),
    ("paper_trade_tags", "ix_paper_trade_tags_trade_created", ("trade_id", "created_at")),
    ("agent_audit_log", "ix_agent_audit_tool_created", ("tool_name", "created_at")),
    ("agent_audit_log", "ix_agent_audit_provider_created", ("provider_name", "created_at")),
    ("notification_events", "ix_notify_scope_channel_seen", ("scope_key", "channel", "last_seen_at")),
    ("notification_events", "ix_notify_symbol_strategy_state", ("symbol", "strategy_key", "signal_state")),
    ("intraday_confirmation_snapshots", "ix_intraday_confirm_date_score", ("trade_date", "score")),
    ("risk_events", "ix_risk_events_account_status_time", ("account_id", "status", "triggered_at")),
    ("sse_subscriptions", "ix_sse_subscriptions_status_seen", ("status", "last_seen_at")),
    ("backtest_runs", "ix_backtest_runs_owner_status_created", ("owner_user_id", "status", "created_at")),
    ("backtest_runs", "ix_backtest_runs_status_dates", ("status", "start_date", "end_date")),
    ("strategy_presets", "ix_strategy_presets_preset_key", ("preset_key",)),
    ("strategy_tier_overrides", "ix_strategy_tier_override_active", ("strategy_key", "reverted_at")),
    ("strategy_tier_override_log", "ix_strategy_tier_override_log_key_created", ("strategy_key", "created_at")),
    ("trading_elasticity_cache", "ix_trading_elasticity_cache_quality_updated", ("data_quality", "updated_at")),
    ("feature_flag_audit_log", "ix_feature_flag_audit_flag_created", ("flag_key", "created_at")),
    ("feature_flag_audit_log", "ix_feature_flag_audit_operator_ip", ("operator_ip",)),
    ("backtest_orders", "ix_backtest_orders_run_date_symbol", ("run_id", "trade_date", "symbol")),
    ("backtest_orders", "ix_backtest_orders_run_strategy_state", ("run_id", "strategy_key", "signal_state")),
    ("backtest_trades", "ix_backtest_trades_run_date_symbol", ("run_id", "trade_date", "symbol")),
    ("backtest_trades", "ix_backtest_trades_strategy_market", ("strategy_key", "market_state", "trade_date")),
    ("backtest_daily_snapshots", "ix_backtest_daily_run_date", ("run_id", "trade_date")),
    ("backtest_dataset_manifests", "ix_backtest_manifest_key_dates", ("dataset_key", "start_date", "end_date")),
    ("backtest_data_quality", "ix_backtest_quality_run_tag", ("run_id", "quality_tag", "severity")),
    ("backtest_data_quality", "ix_backtest_quality_symbol_date", ("symbol", "trade_date")),
    ("backtest_optimizations", "ix_backtest_opt_owner_status_created", ("owner_user_id", "status", "created_at")),
    ("backtest_optimizations", "ix_backtest_opt_strategy_dates", ("strategy_key", "train_start", "test_end")),
    ("backtest_validations", "ix_backtest_val_owner_status_created", ("owner_user_id", "status", "created_at")),
    ("backtest_validations", "ix_backtest_val_strategy_dates", ("strategy_key", "start_date", "end_date")),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    for table_name, index_name, columns in INDEX_SPECS:
        if table_name not in tables:
            continue
        existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
        if any(column not in existing_columns for column in columns):
            continue
        existing_indexes = {item["name"] for item in inspector.get_indexes(table_name)}
        if index_name in existing_indexes:
            continue
        op.create_index(index_name, table_name, list(columns))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    for table_name, index_name, _columns in reversed(INDEX_SPECS):
        if table_name not in tables:
            continue
        existing_indexes = {item["name"] for item in inspector.get_indexes(table_name)}
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name=table_name)
