from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "backend"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.core.database import SessionLocal, init_db
from app.services.strategy_tracking import DEFAULT_RANGE_DAYS
from app.services.strategy_tracking_snapshot import StrategyTrackingSnapshotBuilder


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="只读刷新策略跟踪视图，不回写策略结果或交易账本")
    parser.add_argument("--range", type=int, default=DEFAULT_RANGE_DAYS, dest="range_days")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    init_db()
    with SessionLocal() as db:
        result = StrategyTrackingSnapshotBuilder(db).rebuild_snapshot(range_days=args.range_days)
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2), flush=True)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
