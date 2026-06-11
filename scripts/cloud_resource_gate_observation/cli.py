from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from scripts.cloud_resource_gate_observation.collector import collect_remote
from scripts.cloud_resource_gate_observation.constants import DEFAULT_THRESHOLDS
from scripts.cloud_resource_gate_observation.evaluator import evaluate
from scripts.cloud_resource_gate_observation.report import load_fixture, write_outputs


def parse_thresholds(args: argparse.Namespace) -> dict[str, float]:
    thresholds = dict(DEFAULT_THRESHOLDS)
    if args.worker_memory_warning_pct is not None:
        thresholds["worker_memory_warning_pct"] = args.worker_memory_warning_pct
    if args.worker_memory_blocking_pct is not None:
        thresholds["worker_memory_blocking_pct"] = args.worker_memory_blocking_pct
    return thresholds


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only D5 cloud resource gate observation collector.")
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--ssh-host")
    parser.add_argument("--ssh-user", default="ubuntu")
    parser.add_argument("--ssh-key", type=Path)
    parser.add_argument("--project-dir", default="/home/ubuntu/gupiao-upload")
    parser.add_argument("--app-base-url", default="http://127.0.0.1:18090")
    parser.add_argument("--journal-since", default="24 hours ago")
    parser.add_argument("--docker-logs-since", default="24h")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--checkpoint-label", default="")
    parser.add_argument("--full-trading-day-complete", action="store_true")
    parser.add_argument("--worker-memory-warning-pct", type=float)
    parser.add_argument("--worker-memory-blocking-pct", type=float)
    parser.add_argument("--fail-on-d5-blocked", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.fixture:
        report = load_fixture(args.fixture)
        report.setdefault("source", {})["fixture"] = str(args.fixture)
    elif args.ssh_host:
        report = collect_remote(
            args.ssh_host,
            args.ssh_user,
            args.ssh_key,
            args.project_dir,
            args.app_base_url,
            args.journal_since,
            args.docker_logs_since,
        )
    else:
        raise SystemExit("--fixture or --ssh-host is required")
    thresholds = parse_thresholds(args)
    report["thresholds"] = thresholds
    if args.checkpoint_label:
        report["checkpoint"] = {"label": args.checkpoint_label}
    report["evaluation"] = evaluate(report, thresholds, args.full_trading_day_complete)
    write_outputs(report, args.json_output, args.markdown_output)
    print(json.dumps(report["evaluation"], ensure_ascii=False))
    if args.fail_on_d5_blocked and not report["evaluation"]["d5_gate"]["ready"]:
        return 42
    return 0
