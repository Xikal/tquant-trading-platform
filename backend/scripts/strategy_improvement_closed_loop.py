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
from app.services.strategy_improvement.report import build_closed_loop_report, render_markdown
from app.services.strategy_improvement.types import (
    MIN_DAILY_COVERAGE_PCT,
    MIN_ETF_MINUTE_COVERAGE_PCT,
    MIN_STOCK_SYMBOLS,
    MIN_WF_TRADE_DAYS,
)

DEFAULT_START = "2024-05-28"
DEFAULT_EXISTING_BACKTEST = ROOT_DIR / "docs" / "reports" / "strategy-24m-backtest-2026-05-28.json"
DEFAULT_JSON_OUTPUT = ROOT_DIR / "docs" / "reports" / "strategy-improvement-closed-loop-2026-05-28.json"
DEFAULT_MD_OUTPUT = ROOT_DIR / "docs" / "reports" / "strategy-improvement-closed-loop-2026-05-28.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="策略胜率/盈利率提升闭环只读审计与门禁报告")
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default="")
    parser.add_argument("--existing-backtest", default=str(DEFAULT_EXISTING_BACKTEST))
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MD_OUTPUT))
    parser.add_argument("--min-daily-coverage-pct", type=float, default=MIN_DAILY_COVERAGE_PCT)
    parser.add_argument("--min-stock-symbols", type=int, default=MIN_STOCK_SYMBOLS)
    parser.add_argument("--min-etf-minute-coverage-pct", type=float, default=MIN_ETF_MINUTE_COVERAGE_PCT)
    parser.add_argument("--min-wf-trade-days", type=int, default=MIN_WF_TRADE_DAYS)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    init_db()
    existing_report = _load_json(Path(args.existing_backtest))
    with SessionLocal() as db:
        report = build_closed_loop_report(db, args=args, existing_report=existing_report)

    output_json = Path(args.json_output)
    output_md = Path(args.markdown_output)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "json": str(output_json),
                "markdown": str(output_md),
                "overall_status": report["summary"]["overall_status"],
                "formal_backtest_allowed": report["summary"]["formal_backtest_allowed"],
                "walk_forward_allowed": report["summary"]["walk_forward_allowed"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
