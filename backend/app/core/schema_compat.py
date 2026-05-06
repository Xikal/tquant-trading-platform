from __future__ import annotations

import logging

from sqlalchemy import Column, String, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateColumn

from app.models.base import Base

logger = logging.getLogger(__name__)


def ensure_schema_compatibility(engine: Engine) -> None:
    """Best-effort additive schema repair for self-hosted upgrades.

    `create_all` creates new tables but does not add columns to existing tables.
    This helper keeps production restarts tolerant of additive model changes
    without replacing a formal migration system.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        existing_column_info = {column["name"]: column for column in inspector.get_columns(table.name)}
        existing_columns = set(existing_column_info)
        for column in table.columns:
            if column.name in existing_columns or column.primary_key:
                continue
            _add_nullable_column(engine, table.name, column)
        _widen_strategy_key_column(engine, table.name, existing_column_info)
    _backfill_user_permission_columns(engine, existing_tables)
    _backfill_strategy_metadata_columns(engine, existing_tables)
    _backfill_backtest_owner_columns(engine, existing_tables)
    _ensure_query_indexes(engine, existing_tables)


def _backfill_user_permission_columns(engine: Engine, existing_tables: set[str]) -> None:
    if "users" not in existing_tables:
        return
    user_table = Base.metadata.tables.get("users")
    if user_table is None:
        return
    if "can_paper_trade" not in user_table.columns or "roles" not in user_table.columns:
        return
    try:
        with engine.begin() as connection:
            connection.execute(text("UPDATE users SET can_paper_trade = 1 WHERE can_paper_trade IS NULL"))
            connection.execute(text("UPDATE users SET roles = '' WHERE roles IS NULL"))
    except Exception:
        logger.exception("schema compatibility patch failed to backfill user permission columns")


def _backfill_strategy_metadata_columns(engine: Engine, existing_tables: set[str]) -> None:
    if "strategy_metadata" not in existing_tables:
        return
    try:
        with engine.begin() as connection:
            connection.execute(text("UPDATE strategy_metadata SET enabled = 1 WHERE enabled IS NULL"))
            connection.execute(text("UPDATE strategy_metadata SET probe_status = 'not_required' WHERE probe_status IS NULL OR probe_status = ''"))
            connection.execute(text("UPDATE strategy_metadata SET probe_summary = '' WHERE probe_summary IS NULL"))
            connection.execute(text("UPDATE strategy_metadata SET visibility = 'full' WHERE visibility IS NULL OR visibility = ''"))
            _upsert_strategy_metadata_seed(
                connection,
                key="ma_channel_band",
                name="均线通道波段",
                description="沿 MA20 通道运行的波段研究策略，关注下轨承接与上轨兑现。",
                category="research",
                risk_level="medium",
                holding_days="5-15天",
                sort_order=60,
                probe_status="not_required",
                probe_summary="",
                visibility="full",
            )
            _upsert_strategy_metadata_seed(
                connection,
                key="leader_pullback_band",
                name="龙头回踩波段",
                description="热点龙头确认后回踩均线支撑的二波研究策略。",
                category="research",
                risk_level="high",
                holding_days="3-10天",
                sort_order=70,
                probe_status="pending",
                probe_summary="待样本外验证完成后开放生产入口。",
                visibility="backtest_only",
            )
    except Exception:
        logger.exception("schema compatibility patch failed to backfill strategy metadata columns")


def _upsert_strategy_metadata_seed(
    connection,
    *,
    key: str,
    name: str,
    description: str,
    category: str,
    risk_level: str,
    holding_days: str,
    sort_order: int,
    probe_status: str,
    probe_summary: str,
    visibility: str,
) -> None:
    exists = connection.execute(
        text("SELECT 1 FROM strategy_metadata WHERE `key` = :key LIMIT 1"),
        {"key": key},
    ).scalar()
    if exists:
        connection.execute(
            text(
                """
                UPDATE strategy_metadata
                SET category=:category, enabled=1, probe_status=:probe_status,
                    probe_summary=:probe_summary, visibility=:visibility
                WHERE `key`=:key
                """
            ),
            {
                "key": key,
                "category": category,
                "probe_status": probe_status,
                "probe_summary": probe_summary,
                "visibility": visibility,
            },
        )
        return
    connection.execute(
        text(
            """
            INSERT INTO strategy_metadata (
                `key`, display_name, description, category, risk_level,
                typical_holding_days, sort_order, enabled, probe_status,
                probe_summary, visibility
            )
            VALUES (
                :key, :name, :description, :category, :risk_level,
                :holding_days, :sort_order, 1, :probe_status,
                :probe_summary, :visibility
            )
            """
        ),
        {
            "key": key,
            "name": name,
            "description": description,
            "category": category,
            "risk_level": risk_level,
            "holding_days": holding_days,
            "sort_order": sort_order,
            "probe_status": probe_status,
            "probe_summary": probe_summary,
            "visibility": visibility,
        },
    )


def _backfill_backtest_owner_columns(engine: Engine, existing_tables: set[str]) -> None:
    if "users" not in existing_tables:
        return
    try:
        with engine.begin() as connection:
            system_user_id = _ensure_system_user(connection)
            for table_name in ("backtest_runs", "backtest_optimizations", "backtest_validations"):
                if table_name in existing_tables:
                    connection.execute(
                        text(f"UPDATE {table_name} SET owner_user_id = :user_id WHERE owner_user_id IS NULL"),
                        {"user_id": system_user_id},
                    )
    except Exception:
        logger.exception("schema compatibility patch failed to backfill backtest owner columns")


def _ensure_system_user(connection) -> int:
    existing_id = connection.execute(text("SELECT id FROM users WHERE username = 'system' LIMIT 1")).scalar()
    if existing_id is not None:
        return int(existing_id)
    connection.execute(text(
        """
        INSERT INTO users (username, display_name, password_hash, is_active, can_paper_trade, roles)
        VALUES ('system', '系统管理员', 'disabled-system-user', 0, 0, 'admin')
        """
    ))
    created_id = connection.execute(text("SELECT id FROM users WHERE username = 'system' LIMIT 1")).scalar()
    return int(created_id)


def _add_nullable_column(engine: Engine, table_name: str, source_column) -> None:
    preparer = engine.dialect.identifier_preparer
    ddl_column = Column(source_column.name, source_column.type, nullable=True)
    column_sql = str(CreateColumn(ddl_column).compile(dialect=engine.dialect))
    statement = f"ALTER TABLE {preparer.quote(table_name)} ADD COLUMN {column_sql}"
    try:
        with engine.begin() as connection:
            connection.execute(text(statement))
    except Exception:
        logger.exception("schema compatibility patch failed for %s.%s", table_name, source_column.name)
        return
    logger.info("schema compatibility patch added %s.%s", table_name, source_column.name)


def _widen_strategy_key_column(
    engine: Engine,
    table_name: str,
    existing_columns: dict[str, dict],
) -> None:
    if engine.dialect.name not in {"mysql", "mariadb"}:
        return
    strategy_column = Base.metadata.tables[table_name].columns.get("strategy_key")
    if strategy_column is None or not isinstance(strategy_column.type, String):
        return

    current = existing_columns.get("strategy_key")
    if current is None:
        return
    target_length = int(strategy_column.type.length or 0)
    current_length = int(getattr(current.get("type"), "length", 0) or 0)
    if not target_length or current_length >= target_length:
        return

    preparer = engine.dialect.identifier_preparer
    nullable_sql = "NULL" if current.get("nullable", True) else "NOT NULL"
    statement = (
        f"ALTER TABLE {preparer.quote(table_name)} "
        f"MODIFY COLUMN {preparer.quote('strategy_key')} VARCHAR({target_length}) {nullable_sql}"
    )
    try:
        with engine.begin() as connection:
            connection.execute(text(statement))
    except Exception:
        logger.exception("schema compatibility patch failed to widen %s.strategy_key", table_name)
        return
    logger.info(
        "schema compatibility patch widened %s.strategy_key from %s to %s",
        table_name,
        current_length,
        target_length,
    )


def _ensure_query_indexes(engine: Engine, existing_tables: set[str]) -> None:
    """Create additive indexes used by hot list/read paths.

    The project runs on self-hosted MySQL/SQLite without a formal migration
    runner.  Keep this best-effort and additive so startup can repair older
    deployments without changing table data.
    """

    index_specs = (
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
    inspector = inspect(engine)
    for table_name, index_name, columns in index_specs:
        if table_name not in existing_tables:
            continue
        existing_indexes = {item["name"] for item in inspector.get_indexes(table_name)}
        if index_name in existing_indexes:
            continue
        _create_index(engine, table_name, index_name, columns)


def _create_index(engine: Engine, table_name: str, index_name: str, columns: tuple[str, ...]) -> None:
    table = Base.metadata.tables.get(table_name)
    if table is None:
        return
    missing = [column for column in columns if column not in table.columns]
    if missing:
        return

    preparer = engine.dialect.identifier_preparer
    quoted_columns = ", ".join(preparer.quote(column) for column in columns)
    statement = (
        f"CREATE INDEX {preparer.quote(index_name)} "
        f"ON {preparer.quote(table_name)} ({quoted_columns})"
    )
    try:
        with engine.begin() as connection:
            connection.execute(text(statement))
    except Exception:
        logger.exception("schema compatibility patch failed to create index %s", index_name)
        return
    logger.info("schema compatibility patch created index %s on %s", index_name, table_name)
