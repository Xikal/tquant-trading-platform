#!/usr/bin/env python3
"""Validate the D5 gate before embedded runtime-scheduler deployment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


BLOCKED_EXIT_CODE = 42


def load_summary(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    if not path.exists():
        return None, [f"summary_not_found={path}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"invalid_json={exc.msg}"]
    if not isinstance(payload, dict):
        return None, ["summary_json_must_be_object"]
    return payload, []


def normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def evaluate_summary(summary: dict[str, Any] | None, load_errors: list[str]) -> dict[str, Any]:
    blocking = list(load_errors)
    if summary is None:
        return {
            "ok": False,
            "status": "blocked",
            "blocking": blocking,
        }

    missing_checkpoints = normalize_list(summary.get("missing_checkpoints"))
    d5_blockers = normalize_list(summary.get("d5_blockers"))
    full_trading_day_complete = summary.get("full_trading_day_complete") is True
    d5_ready = summary.get("d5_ready") is True

    if not d5_ready:
        blocking.append("d5_ready=false")
    if not full_trading_day_complete:
        blocking.append("full_trading_day_complete=false")
    if missing_checkpoints:
        blocking.append("missing_checkpoints=" + ",".join(missing_checkpoints))
    blocking.extend(f"d5_blocker={item}" for item in d5_blockers)

    ok = not blocking
    return {
        "ok": ok,
        "status": "ready" if ok else "blocked",
        "blocking": blocking,
        "checkpoint_count": summary.get("checkpoint_count"),
        "required_checkpoints": normalize_list(summary.get("required_checkpoints")),
        "observed_checkpoints": normalize_list(summary.get("observed_checkpoints")),
        "missing_checkpoints": missing_checkpoints,
        "d5_blockers": d5_blockers,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read a local D5 trading-day gate summary JSON and block embedded "
            "runtime-scheduler deployment unless it is fully ready."
        )
    )
    parser.add_argument(
        "--summary",
        required=True,
        type=Path,
        help="Path to cloud-resource-trading-day-gate-summary-*.json",
    )
    parser.add_argument(
        "--fail-on-blocked",
        action="store_true",
        help=f"Exit {BLOCKED_EXIT_CODE} when the gate is not ready.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary_path = args.summary.expanduser()
    summary, load_errors = load_summary(summary_path)
    result = evaluate_summary(summary, load_errors)
    result["summary_path"] = str(summary_path)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if args.fail_on_blocked and not result["ok"]:
        return BLOCKED_EXIT_CODE
    return 0


if __name__ == "__main__":
    sys.exit(main())
