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
from app.services.data_quality.repair import repair_invalid_ohlc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="幂等修复无效 OHLC 日线，默认 dry-run，不臆造价格")
    parser.add_argument("--dataset", choices=("daily_bars",), required=True)
    parser.add_argument("--as-of", default="", help="保留参数，审计用；当前检测全库无效 OHLC。")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="只输出待修复清单，不改库")
    mode.add_argument("--apply", action="store_true", help="执行修复：先备份，重抓失败才删除无歧义脏行")
    parser.add_argument("--output", default="", help="审计 JSON 输出路径")
    parser.add_argument("--backup-dir", default="", help="数据库和行级备份目录")
    parser.add_argument("--operator", default="cli")
    parser.add_argument("--no-refetch", action="store_true", help="跳过重抓尝试，仅在 apply 时备份后删除无歧义脏行")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    dry_run = not args.apply
    init_db()
    with SessionLocal() as db:
        result = repair_invalid_ohlc(
            db,
            dataset_key=args.dataset,
            dry_run=dry_run,
            backup_dir=args.backup_dir or None,
            output_path=args.output or None,
            refetch=not args.no_refetch,
            operator=args.operator,
        )
    print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
