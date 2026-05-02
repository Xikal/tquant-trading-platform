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
        ("watchlist_signal_snapshots", "ix_watchlist_signal_updated", ("updated_at", "symbol")),
        ("low_buy_trade_lifecycle_snapshots", "ix_lb_lifecycle_scope_status_date", ("user_scope", "status", "signal_trade_date")),
        ("paper_positions", "ix_paper_positions_account_symbol", ("account_id", "symbol")),
        ("paper_orders", "ix_paper_orders_account_created", ("account_id", "created_at")),
        ("paper_trades", "ix_paper_trades_account_time", ("account_id", "trade_time")),
        ("intraday_confirmation_snapshots", "ix_intraday_confirm_date_score", ("trade_date", "score")),
        ("risk_events", "ix_risk_events_account_status_time", ("account_id", "status", "triggered_at")),
        ("sse_subscriptions", "ix_sse_subscriptions_status_seen", ("status", "last_seen_at")),
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
