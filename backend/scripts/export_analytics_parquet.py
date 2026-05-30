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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="导出分析层 Parquet 数据集")
    parser.add_argument("--dataset", choices=("daily_bars",), default="daily_bars")
    parser.add_argument("--months", type=int, default=24)
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument("--output-root", default="backend/data/analytics")
    parser.add_argument("--write-manifest", action="store_true", default=True)
    parser.add_argument("--no-create-backfill-task", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    init_db()
    with SessionLocal() as db:
        manifest = export_daily_bars_parquet(
            db,
            months=args.months,
            end_date=date.fromisoformat(args.end_date[:10]),
            output_root=args.output_root,
            create_backfill_task=not args.no_create_backfill_task,
        )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if manifest.get("quality", {}).get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
