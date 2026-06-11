#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.cloud_resource_gate_observation.summary import (  # noqa: E402
    load_reports,
    render_summary_markdown,
    summarize_reports,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize read-only D5 trading-day gate snapshots.")
    parser.add_argument("snapshots", nargs="+", type=Path)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--fail-on-d5-blocked", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    reports = load_reports(args.snapshots)
    summary = summarize_reports(reports)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_summary_markdown(summary, reports), encoding="utf-8")
    print(json.dumps({"d5_ready": summary["d5_ready"], "d5_blockers": summary["d5_blockers"]}, ensure_ascii=False))
    if args.fail_on_d5_blocked and not summary["d5_ready"]:
        return 42
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
