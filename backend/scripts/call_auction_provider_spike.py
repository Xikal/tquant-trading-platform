from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "backend"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.core.timezone import beijing_now
from app.services.auction.provider_spike import (
    DEFAULT_PROVIDER_TIMEOUT_SECONDS,
    SOURCE_NAME,
    SpikeSymbolResult,
    fetch_akshare_pre_min_symbol,
    fetch_symbol_with_timeout,
    inspect_pre_min_records,
    instrument_type_for_symbol,
    load_target_symbols,
    market_for_symbol,
    missing_sample_buckets,
    parse_beijing_datetime,
    run_spike,
    sample_coverage,
    select_sample_symbols,
    write_report,
)

DEFAULT_OUTPUT_MD = ROOT_DIR / "docs" / "reports" / "call-auction-provider-spike-latest.md"
DEFAULT_OUTPUT_JSON = ROOT_DIR / "backend" / "data" / "reports" / "call-auction-provider-spike-latest.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="集合竞价 provider 小样本 spike。窗口外只生成 blocked 报告。")
    parser.add_argument("--sample-size", type=int, default=30, help="抽样标的数量，默认 30，建议 10-30")
    parser.add_argument("--symbols", default="", help="可选，逗号分隔标的；为空则从 quote-cache demand 集合抽样")
    parser.add_argument("--now", default="", help="测试/复现用，北京时间 ISO 字符串；默认当前北京时间")
    parser.add_argument("--sleep", type=float, default=0.1, help="每只 provider 调用后的间隔秒数，默认 0.1")
    parser.add_argument(
        "--provider-timeout",
        type=float,
        default=DEFAULT_PROVIDER_TIMEOUT_SECONDS,
        help=f"单只 provider 调用超时秒数，默认 {DEFAULT_PROVIDER_TIMEOUT_SECONDS}",
    )
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD), help="Markdown 报告输出路径")
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON), help="JSON 报告输出路径")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    now = parse_beijing_datetime(args.now) if args.now else beijing_now()
    symbols = load_target_symbols(raw_symbols=args.symbols, sample_size=args.sample_size)
    report = run_spike(
        symbols=symbols,
        now=now,
        sleep_seconds=max(float(args.sleep or 0.0), 0.0),
        provider_timeout_seconds=max(float(args.provider_timeout or 0.0), 0.0),
    )
    write_report(report, markdown_path=Path(args.output_md), json_path=Path(args.output_json))
    print(
        json.dumps(
            {
                "status": report["status"],
                "conclusion": report["conclusion"],
                "symbols": len(report["symbols"]),
                "markdown_path": str(args.output_md),
                "json_path": str(args.output_json),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0


__all__ = [
    "SOURCE_NAME",
    "DEFAULT_PROVIDER_TIMEOUT_SECONDS",
    "SpikeSymbolResult",
    "fetch_akshare_pre_min_symbol",
    "fetch_symbol_with_timeout",
    "inspect_pre_min_records",
    "instrument_type_for_symbol",
    "main",
    "market_for_symbol",
    "missing_sample_buckets",
    "run_spike",
    "sample_coverage",
    "select_sample_symbols",
    "write_report",
]


if __name__ == "__main__":
    raise SystemExit(main())
