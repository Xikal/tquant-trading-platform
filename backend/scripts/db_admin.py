from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "backend"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.services.db_admin_service import DatabaseAdminService
from app.services.settings_service import SettingsService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="数据库管理工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="检测数据库连接")
    check_parser.add_argument("--url", required=True, help="目标数据库 URL")

    migrate_parser = subparsers.add_parser("migrate", help="迁移 SQLite 数据到目标数据库")
    migrate_parser.add_argument("--target-url", required=True, help="目标数据库 URL")
    migrate_parser.add_argument(
        "--source-url",
        default="sqlite:///./data/t_quant.db",
        help="源数据库 URL，默认当前本地 SQLite",
    )
    migrate_parser.add_argument("--overwrite", action="store_true", help="迁移前清空目标库已有数据")
    migrate_parser.add_argument(
        "--activate",
        action="store_true",
        help="迁移完成后写入 runtime.env，重启后端即切换到目标数据库",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    service = DatabaseAdminService()

    if args.command == "check":
        result = service.check_connection(args.url)
        print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
        return 0

    result = service.migrate_data(
        source_database_url=args.source_url,
        target_database_url=args.target_url,
        overwrite=args.overwrite,
    )
    if args.activate:
        SettingsService.persist_runtime_database_url(args.target_url)
        result.activated_on_restart = True
        result.message = "数据迁移完成，目标数据库已写入 runtime.env，重启后端后生效。"
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
