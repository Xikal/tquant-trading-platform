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
    # Query/index changes are intentionally not repaired here.  Production
    # deployments must apply Alembic migrations so versioning, downgrade paths,
    # and MySQL validation stay explicit.


def verify_schema_compatibility(engine: Engine) -> None:
    """Log additive schema drift without mutating the database.

    Production deployments should apply Alembic migrations before starting the
    app.  This read-only check keeps startup observable while avoiding hidden
    DDL/DML in Web workers.
    """

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    missing_tables: list[str] = []
    missing_columns: list[str] = []
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            missing_tables.append(table.name)
            continue
        existing_columns = {column["name"] for column in inspector.get_columns(table.name)}
        missing_columns.extend(
            f"{table.name}.{column.name}"
            for column in table.columns
            if column.name not in existing_columns and not column.primary_key
        )
    if missing_tables:
        logger.warning(
            "schema compatibility check found missing tables; run Alembic migrations before starting production: %s",
            ", ".join(missing_tables[:20]),
        )
    if missing_columns:
        logger.warning(
            "schema compatibility check found missing columns; run Alembic migrations or set "
            "SCHEMA_COMPAT_REPAIR_ENABLED=true for one-time self-hosted repair: %s",
            ", ".join(missing_columns[:20]),
        )


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
