#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_DIR = PROJECT_ROOT / ".runtime" / "warning-budget"


@dataclass(frozen=True)
class WarningAllowance:
    warning_type: str
    message_pattern: str
    path_pattern: str
    max_count: int
    reason: str


ALLOWANCES = (
    WarningAllowance(
        warning_type="NotOpenSSLWarning",
        message_pattern=r"urllib3 v2 only supports OpenSSL 1\.1\.1\+",
        path_pattern=r"/urllib3/__init__\.py$",
        max_count=1,
        reason="macOS system Python in this workspace is linked against LibreSSL; this is an environment warning, not project runtime behavior.",
    ),
)


def main() -> int:
    args = parse_args()
    report_dir = Path(args.report_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    report = run_warning_budget(args)
    stamp = time.strftime("%Y-%m-%d-%H%M%S")
    report_path = report_dir / f"warning-budget-{stamp}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report_path)
    if not report["ok"]:
        print(render_failures(report), file=sys.stderr)
    return 0 if report["ok"] else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run pytest with an explicit warning budget.")
    parser.add_argument("pytest_args", nargs="*", default=["backend/tests"], help="Arguments passed to pytest.")
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--python", default=str(resolve_backend_python()))
    return parser.parse_args()


def run_warning_budget(args: argparse.Namespace) -> dict:
    command = [args.python, "-m", "pytest", *args.pytest_args, "-W", "always", "-ra"]
    started = time.time()
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=900,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "backend")},
    )
    warning_items = warnings_from_pytest_output(completed.stdout)
    budget = evaluate_budget(warning_items)
    ok = completed.returncode == 0 and not budget["violations"]
    return {
        "ok": ok,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "command": " ".join(command),
        "elapsed_ms": int((time.time() - started) * 1000),
        "pytest_exit_code": completed.returncode,
        "warning_count": len(warning_items),
        "warnings": warning_items,
        "budget": budget,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def warnings_from_pytest_output(stdout: str) -> list[dict]:
    warnings: list[dict] = []
    pattern = re.compile(r"^\s+(?P<filename>.+?):(?P<lineno>\d+):\s+(?P<category>[A-Za-z_][\w.]*Warning):\s+(?P<message>.+)$")
    count_pattern = re.compile(r"^\S.*:\s+(?P<count>\d+)\s+warnings$")
    pending_count = 1
    for line in stdout.splitlines():
        count_match = count_pattern.match(line.strip())
        if count_match:
            pending_count = int(count_match.group("count"))
            continue
        match = pattern.match(line)
        if not match:
            continue
        warnings.append(
            {
                "category": match.group("category"),
                "message": match.group("message").strip(),
                "filename": match.group("filename").strip(),
                "lineno": int(match.group("lineno")),
                "count": pending_count,
            }
        )
        pending_count = 1
    return warnings


def evaluate_budget(warnings: list[dict]) -> dict:
    allowance_results = []
    allowed_indexes: set[int] = set()
    violations: list[dict] = []
    for allowance in ALLOWANCES:
        matching_indexes = [
            index
            for index, warning in enumerate(warnings)
            if warning["category"] == allowance.warning_type
            and re.search(allowance.message_pattern, warning["message"])
            and re.search(allowance.path_pattern, warning["filename"])
        ]
        match_count = sum(int(warnings[index].get("count") or 1) for index in matching_indexes)
        for index in matching_indexes:
            allowed_indexes.add(index)
        if match_count > allowance.max_count:
            violations.append(
                {
                    "type": "allowance_exceeded",
                    "warning_type": allowance.warning_type,
                    "count": match_count,
                    "max_count": allowance.max_count,
                    "reason": allowance.reason,
                }
            )
        allowance_results.append(
            {
                "warning_type": allowance.warning_type,
                "max_count": allowance.max_count,
                "matched_count": match_count,
                "reason": allowance.reason,
            }
        )
    for index, warning in enumerate(warnings):
        if index not in allowed_indexes:
            violations.append({"type": "unexpected_warning", "warning": warning})
    return {
        "allowed_warning_count": sum(int(warnings[index].get("count") or 1) for index in allowed_indexes),
        "unexpected_warning_count": sum(
            int(item["warning"].get("count") or 1) for item in violations if item["type"] == "unexpected_warning"
        ),
        "allowances": allowance_results,
        "violations": violations,
    }


def render_failures(report: dict) -> str:
    lines = ["warning-budget failed:"]
    if report["pytest_exit_code"] != 0:
        lines.append(f"- pytest exited with {report['pytest_exit_code']}")
    for violation in report["budget"]["violations"][:20]:
        lines.append(f"- {violation}")
    return "\n".join(lines)


def resolve_backend_python() -> Path:
    local = PROJECT_ROOT / "backend" / ".venv" / "bin" / "python"
    return local if local.exists() else Path(sys.executable).resolve()


if __name__ == "__main__":
    raise SystemExit(main())
