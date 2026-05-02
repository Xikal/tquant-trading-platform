from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import create_engine, delete, inspect, select, text
from sqlalchemy.orm import sessionmaker

from app.core.database import _sqlite_connect_args
from app.models.base import Base
from app.models.entities import (
    AnalysisLog,
    BacktestRun,
    DailyBarSnapshot,
    Instrument,
    InstrumentRule,
    LowBuyCloseReviewSnapshot,
    LowBuyHotIndustrySnapshot,
    LowBuyResultSnapshot,
    LowBuyScanSnapshot,
    LowBuyStrategyPerformanceSnapshot,
    LowBuyStrategyPerformanceWindowSnapshot,
    LowBuyPoolSnapshot,
    MarketEventCache,
    MinuteBarSnapshot,
    SignalReplay,
    SystemSetting,
    Watchlist,
    WatchlistSignalSnapshot,
)
from app.models.schemas import DatabaseCheckResponse, DatabaseMigrationResponse

MODEL_COPY_ORDER = [
    Instrument,
    InstrumentRule,
    Watchlist,
    WatchlistSignalSnapshot,
    SystemSetting,
    AnalysisLog,
    SignalReplay,
    BacktestRun,
    MarketEventCache,
    MinuteBarSnapshot,
    DailyBarSnapshot,
    LowBuyPoolSnapshot,
    LowBuyHotIndustrySnapshot,
    LowBuyScanSnapshot,
    LowBuyResultSnapshot,
    LowBuyStrategyPerformanceSnapshot,
    LowBuyStrategyPerformanceWindowSnapshot,
    LowBuyCloseReviewSnapshot,
]


@dataclass
class EngineBundle:
    engine: object
    session_factory: sessionmaker


class DatabaseAdminService:
    def _build_engine_bundle(self, database_url: str) -> EngineBundle:
        engine = create_engine(
            database_url,
            future=True,
            pool_pre_ping=True,
            connect_args=_sqlite_connect_args(database_url),
        )
        return EngineBundle(
            engine=engine,
            session_factory=sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True),
        )

    @staticmethod
    def mask_database_url(database_url: str) -> str:
        if "@" not in database_url or "://" not in database_url:
            return database_url
        scheme, rest = database_url.split("://", 1)
        credentials, suffix = rest.split("@", 1)
        if ":" not in credentials:
            return f"{scheme}://***@{suffix}"
        username, _ = credentials.split(":", 1)
        return f"{scheme}://{username}:***@{suffix}"

    def check_connection(self, database_url: str) -> DatabaseCheckResponse:
        bundle = self._build_engine_bundle(database_url)
        try:
            with bundle.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            inspector = inspect(bundle.engine)
            tables = sorted(inspector.get_table_names())
            return DatabaseCheckResponse(
                ok=True,
                dialect=bundle.engine.url.get_backend_name(),
                database=bundle.engine.url.database or "",
                masked_url=self.mask_database_url(database_url),
                tables=tables,
                message="数据库连接成功。",
            )
        finally:
            bundle.engine.dispose()

    def migrate_data(
        self,
        source_database_url: str,
        target_database_url: str,
        overwrite: bool = False,
    ) -> DatabaseMigrationResponse:
        if source_database_url == target_database_url:
            raise ValueError("源数据库与目标数据库不能相同。")

        source_bundle = self._build_engine_bundle(source_database_url)
        target_bundle = self._build_engine_bundle(target_database_url)

        Base.metadata.create_all(bind=target_bundle.engine)

        source_session = source_bundle.session_factory()
        target_session = target_bundle.session_factory()

        try:
            if overwrite:
                for model in reversed(MODEL_COPY_ORDER):
                    target_session.execute(delete(model))
                target_session.commit()
            else:
                occupied = {}
                for model in MODEL_COPY_ORDER:
                    count = target_session.execute(select(model)).scalars().first()
                    if count is not None:
                        occupied[model.__tablename__] = 1
                if occupied:
                    names = "、".join(sorted(occupied))
                    raise ValueError(f"目标数据库已存在数据，请先清空或勾选覆盖迁移：{names}")

            copied_rows: dict[str, int] = {}
            total_rows = 0
            for model in MODEL_COPY_ORDER:
                rows = source_session.execute(select(model)).scalars().all()
                copied_rows[model.__tablename__] = len(rows)
                for row in rows:
                    payload = {
                        column.name: getattr(row, column.name)
                        for column in model.__table__.columns
                    }
                    target_session.merge(model(**payload))
                target_session.commit()
                total_rows += len(rows)

            return DatabaseMigrationResponse(
                ok=True,
                source_database_url=source_database_url,
                target_database_url=target_database_url,
                copied_rows=copied_rows,
                total_rows=total_rows,
                activated_on_restart=False,
                message="数据迁移完成。",
            )
        finally:
            source_session.close()
            target_session.close()
            source_bundle.engine.dispose()
            target_bundle.engine.dispose()
