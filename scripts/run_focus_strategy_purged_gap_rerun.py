#!/usr/bin/env python3
"""Run focused strategy purged-gap rerun manifest commands with resumable summary."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DATE = "2026-05-28"


def run_manifest(
    *,
    report_date: str = REPORT_DATE,
    root: Path = ROOT,
    limit: int = 0,
    keep_going: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    manifest = _load_manifest(root=root, report_date=report_date)
    commands = list(manifest.get("commands") or [])
    if limit > 0:
        commands = commands[:limit]
    records: list[dict[str, Any]] = []
    started_at = time.time()
    for index, item in enumerate(commands, start=1):
        expected = _expected_json_path(item["command"], root=root)
        if expected.exists() and not force:
            records.append(_record(item, index=index, status="skipped_existing", expected=expected, seconds=0.0, returncode=0))
            continue
        if expected.exists() and force:
            expected.unlink()
            markdown = expected.with_suffix(".md")
            if markdown.exists():
                markdown.unlink()
        before = time.time()
        result = subprocess.run(item["command"], shell=True, cwd=root, text=True, capture_output=True)
        seconds = round(time.time() - before, 3)
        status = "passed" if result.returncode == 0 and expected.exists() else "failed"
        records.append(
            _record(
                item,
                index=index,
                status=status,
                expected=expected,
                seconds=seconds,
                returncode=result.returncode,
                stdout_tail=_tail(result.stdout),
                stderr_tail=_tail(result.stderr),
            )
        )
        if status == "failed" and not keep_going:
            break
    summary = _summary(report_date=report_date, root=root, manifest=manifest, records=records, started_at=started_at)
    out_path = root / "docs" / "reports" / f"focus-strategy-purged-gap-rerun-{report_date}" / "run-summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def _load_manifest(*, root: Path, report_date: str) -> dict[str, Any]:
    path = root / "docs" / "reports" / f"focus-strategy-purged-gap-audit-{report_date}" / "summary.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["rerun_manifest"]


def _expected_json_path(command: str, *, root: Path) -> Path:
    parts = shlex.split(command)
    output_dir = _arg(parts, "--matrix-output-dir") or _arg(parts, "--output-dir") or "."
    states = (_arg(parts, "--states") or "all").replace(",", "_").replace("/", "_")
    strategies = (_arg(parts, "--strategies") or "all").replace(",", "_").replace("/", "_")
    start = _arg(parts, "--start") or "auto"
    end = _arg(parts, "--end") or "auto"
    max_dates = _arg(parts, "--max-dates")
    suffix = f"_{max_dates}d" if max_dates and int(max_dates) > 0 else ""
    stem = f"low_buy_execution_matrix_24m_{states}_{strategies}_{start}_{end}{suffix}.json"
    return root / output_dir / stem


def _arg(parts: list[str], name: str) -> str:
    try:
        index = parts.index(name)
    except ValueError:
        return ""
    return parts[index + 1] if index + 1 < len(parts) else ""


def _record(
    item: dict[str, Any],
    *,
    index: int,
    status: str,
    expected: Path,
    seconds: float,
    returncode: int,
    stdout_tail: str = "",
    stderr_tail: str = "",
) -> dict[str, Any]:
    return {
        "index": index,
        "scope_key": item.get("scope_key"),
        "window_id": item.get("window_id"),
        "oos_start": item.get("oos_start"),
        "oos_end": item.get("oos_end"),
        "status": status,
        "returncode": returncode,
        "seconds": seconds,
        "output_json": str(expected.relative_to(ROOT)) if expected.is_relative_to(ROOT) else str(expected),
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
    }


def _summary(
    *,
    report_date: str,
    root: Path,
    manifest: dict[str, Any],
    records: list[dict[str, Any]],
    started_at: float,
) -> dict[str, Any]:
    passed = sum(1 for item in records if item["status"] == "passed")
    skipped = sum(1 for item in records if item["status"] == "skipped_existing")
    failed = sum(1 for item in records if item["status"] == "failed")
    return {
        "title": "P1 重点策略 purged-gap manifest 复跑执行记录",
        "report_date": report_date,
        "database_url": manifest.get("database_url"),
        "manifest_command_count": manifest.get("command_count"),
        "executed_or_existing_count": passed + skipped,
        "passed_count": passed,
        "skipped_existing_count": skipped,
        "failed_count": failed,
        "complete": failed == 0 and (passed + skipped) == int(manifest.get("command_count") or 0),
        "seconds": round(time.time() - started_at, 3),
        "records": records,
        "output_dir": manifest.get("output_dir"),
        "summary_path": str(
            (root / "docs" / "reports" / f"focus-strategy-purged-gap-rerun-{report_date}" / "run-summary.json").relative_to(root)
        ),
    }


def _tail(value: str, *, limit: int = 1200) -> str:
    return value[-limit:] if len(value) > limit else value


def main() -> None:
    parser = argparse.ArgumentParser(description="Run focused purged-gap manifest commands.")
    parser.add_argument("--date", default=REPORT_DATE)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--keep-going", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    summary = run_manifest(report_date=args.date, limit=args.limit, keep_going=args.keep_going, force=args.force)
    print(json.dumps({key: summary[key] for key in ("complete", "executed_or_existing_count", "failed_count", "seconds")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
