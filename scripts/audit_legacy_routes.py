#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY_PATHS = ("/backtests", "/research")
SCAN_ROOTS = ("backend/app", "scripts")
DEFAULT_EXCLUDES = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
}
ALLOWED_REFERENCE_FILES = {
    "backend/app/main.py",
    "backend/app/api/routes/backtests.py",
    "backend/app/api/routes/research.py",
    "backend/tests/test_legacy_routes.py",
    "docs/operations/legacy-route-removal.md",
    "docs/superpowers/plans/2026-05-06-high-risk-optimization-plan.md",
    "IMPLEMENTATION_PLAN.md",
    "scripts/audit_legacy_routes.py",
}
ALLOWED_REFERENCE_PREFIXES = (
)


def audit_legacy_route_usage(root: Path = ROOT) -> dict[str, object]:
    findings: list[dict[str, object]] = []
    for scan_root in SCAN_ROOTS:
        base = root / scan_root
        if not base.exists():
            continue
        for path in _iter_text_files(base, root):
            findings.extend(_scan_file(path, root))
    return {
        "status": "ok" if not findings else "needs_review",
        "legacy_paths": list(LEGACY_PATHS),
        "finding_count": len(findings),
        "findings": findings,
    }


def _scan_file(path: Path, root: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    pattern = re.compile(r'(?<!/api)(["\'`])(/backtests|/research)\1')
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return []
    for line_no, line in enumerate(lines, start=1):
        for match in pattern.finditer(line):
            findings.append(
                {
                    "file": str(path.relative_to(root)),
                    "line": line_no,
                    "legacy_path": match.group(2),
                    "text": line.strip()[:240],
                }
            )
    return findings


def _iter_text_files(base: Path, root: Path):
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        relative = str(path.relative_to(root))
        if relative in ALLOWED_REFERENCE_FILES:
            continue
        if any(relative.startswith(prefix) for prefix in ALLOWED_REFERENCE_PREFIXES):
            continue
        if any(part in DEFAULT_EXCLUDES for part in path.parts):
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".db", ".sqlite", ".zip", ".gz", ".apk", ".mp4"}:
            continue
        yield path

def main() -> int:
    parser = argparse.ArgumentParser(description="Audit first-party references to legacy frontend routes.")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when references are found.")
    args = parser.parse_args()
    report = audit_legacy_route_usage()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if args.strict and report["finding_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
