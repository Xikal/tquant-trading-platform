from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "backend"
DEFAULT_REPORT_OUTPUT = ROOT_DIR / "docs" / "reports" / "etf-t0-rule-sync-2026-05-28.json"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.core.database import SessionLocal, init_db
from app.services.etf.rule_sync import sync_etf_t0_rules


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="将 ETF universe 的 T+0 白名单持久化到 instrument_rules")
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT_OUTPUT))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    init_db()
    with SessionLocal() as db:
        report = sync_etf_t0_rules(db)
    output = Path(args.report_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(output), "t0_enabled_count": report["t0_enabled_count"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
