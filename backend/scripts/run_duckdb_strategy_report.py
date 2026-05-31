from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal, init_db
from app.services.analytics.exporters import export_daily_bars_parquet
from app.services.analytics.manifest import load_manifest
from app.services.analytics.report_queries import build_strategy_24m_duckdb_report, write_strategy_24m_report
from app.services.data_quality.snapshots import data_quality_sla_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="基于 DuckDB 生成 24个月策略报告")
    parser.add_argument("--months", type=int, default=24)
    parser.add_argument("--manifest", default="latest")
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument("--output-root", default="backend/data/analytics")
    parser.add_argument("--strategy-report-json", default="")
    parser.add_argument("--output-md", default="docs/reports/strategy_24m_duckdb_report.md")
    parser.add_argument("--output-json", default="backend/data/analytics/reports/strategy_24m_duckdb_report.json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    init_db()
    if args.manifest == "latest":
        with SessionLocal() as db:
            manifest = export_daily_bars_parquet(
                db,
                months=args.months,
                end_date=date.fromisoformat(args.end_date[:10]),
                output_root=args.output_root,
                create_backfill_task=True,
            )
    else:
        manifest = load_manifest(args.manifest, output_root=args.output_root)
    with SessionLocal() as db:
        sla_payload = data_quality_sla_payload(db)
    report = build_strategy_24m_duckdb_report(
        manifest,
        output_root=args.output_root,
        legacy_strategy_report=args.strategy_report_json or None,
        data_quality_sla=sla_payload,
    )
    write_strategy_24m_report(report, output_md=args.output_md, output_json=args.output_json)
    print(json.dumps({"status": report["status"], "output_md": args.output_md, "output_json": args.output_json}, ensure_ascii=False))
    return 0 if report.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
