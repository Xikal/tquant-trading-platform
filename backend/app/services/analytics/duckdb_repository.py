from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.analytics.config import analytics_config


class DuckDBRepository:
    def __init__(self, *, output_root: str | Path | None = None, threads: int | None = None) -> None:
        try:
            import duckdb  # type: ignore
        except Exception as exc:  # pragma: no cover - exercised when optional dep missing
            raise RuntimeError("缺少 duckdb 依赖，请先安装 backend/requirements-analytics.txt。") from exc
        self.config = analytics_config(output_root)
        self.connection = duckdb.connect(database=":memory:")
        self.connection.execute(f"PRAGMA threads={threads or self.config.duckdb_threads}")

    def query_one(self, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        cursor = self.connection.execute(sql, params or {})
        columns = [item[0] for item in cursor.description]
        row = cursor.fetchone()
        return dict(zip(columns, row)) if row else {}

    def query_all(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        cursor = self.connection.execute(sql, params or {})
        columns = [item[0] for item in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def close(self) -> None:
        self.connection.close()
