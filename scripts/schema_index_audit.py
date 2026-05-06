#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import SQLAlchemyError


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402


@dataclass(frozen=True)
class ExpectedIndex:
    table: str
    columns: tuple[str, ...]
    purpose: str


EXPECTED_INDEXES: tuple[ExpectedIndex, ...] = (
    ExpectedIndex("low_buy_result_snapshots", ("latest_trade_date", "strategy_key", "score"), "priority board latest ranking"),
    ExpectedIndex("low_buy_result_snapshots", ("latest_trade_date", "strategy_key", "buy_signal_state", "score"), "priority board signal-state filtering"),
    ExpectedIndex("low_buy_result_snapshots", ("strategy_key", "symbol", "latest_trade_date"), "per-symbol strategy signal history"),
    ExpectedIndex("low_buy_scan_snapshots", ("strategy_key", "latest_trade_date", "updated_at"), "latest low-buy scan lookup"),
    ExpectedIndex("low_buy_strategy_pool_snapshots", ("latest_trade_date", "strategy_key", "pool_key", "rank_score"), "strategy pool latest lookup"),
    ExpectedIndex("paper_performance_snapshots", ("account_id", "snapshot_date"), "paper dashboard equity curve"),
    ExpectedIndex("paper_strategy_perf_daily", ("account_id", "trade_date", "strategy_key"), "paper strategy daily metrics"),
    ExpectedIndex("paper_market_state_perf_daily", ("account_id", "trade_date", "market_state"), "paper market-state daily metrics"),
    ExpectedIndex("backtest_runs", ("owner_user_id", "status", "created_at"), "user backtest list"),
    ExpectedIndex("backtest_runs", ("status", "start_date", "end_date"), "backtest worker/status filtering"),
    ExpectedIndex("runtime_tasks", ("status", "priority", "id"), "runtime worker polling"),
    ExpectedIndex("runtime_tasks", ("task_type", "status"), "runtime task type filtering"),
    ExpectedIndex("feature_flag_audit_log", ("flag_key", "created_at"), "feature flag audit history"),
)


def audit_schema_indexes(database_url: str | None = None) -> dict[str, Any]:
    """Return a structured report of missing hot-path indexes.

    The script is read-only by design.  Missing indexes should be materialized
    through Alembic migrations, not by app startup compatibility code.
    """

    url = database_url or get_settings().database_url
    engine = create_engine(url, future=True)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
    except SQLAlchemyError as exc:
        return {
            "status": "unavailable",
            "database_dialect": engine.dialect.name,
            "expected_count": len(EXPECTED_INDEXES),
            "present_count": 0,
            "missing_table_count": 0,
            "missing_index_count": 0,
            "missing_tables": [],
            "missing_indexes": [],
            "error": str(exc).splitlines()[0][:240],
        }
    missing_tables: list[dict[str, Any]] = []
    missing_indexes: list[dict[str, Any]] = []
    present: list[dict[str, Any]] = []

    for spec in EXPECTED_INDEXES:
        payload = asdict(spec)
        payload["columns"] = list(spec.columns)
        if spec.table not in tables:
            missing_tables.append(payload)
            continue
        indexes = inspector.get_indexes(spec.table)
        indexed_columns = {tuple(index.get("column_names") or ()) for index in indexes}
        if spec.columns in indexed_columns:
            present.append(payload)
        else:
            missing_indexes.append(payload)

    return {
        "status": "ok" if not missing_tables and not missing_indexes else "degraded",
        "database_dialect": engine.dialect.name,
        "expected_count": len(EXPECTED_INDEXES),
        "present_count": len(present),
        "missing_table_count": len(missing_tables),
        "missing_index_count": len(missing_indexes),
        "missing_tables": missing_tables,
        "missing_indexes": missing_indexes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit expected hot-path database indexes.")
    parser.add_argument("--database-url", default="", help="Override DATABASE_URL for audit only.")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when missing indexes/tables are found.")
    args = parser.parse_args()
    report = audit_schema_indexes(args.database_url or None)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if args.strict and report["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
