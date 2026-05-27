#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BENCH_RE = re.compile(r"test (?P<name>\S+) \.\.\. bench:\s+(?P<value>[0-9,]+)\s+ns/iter")


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: check_rust_bench_baseline.py <baseline.json> <bench-output.txt>", file=sys.stderr)
        return 2
    baseline_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    results = parse_results(output_path.read_text(encoding="utf-8", errors="replace"))
    failures: list[str] = []
    missing: list[str] = []
    for name, config in baseline.get("benchmarks", {}).items():
        max_ns = int(config.get("max_ns_per_iter") or 0)
        actual = results.get(name)
        if actual is None:
            missing.append(name)
            continue
        if max_ns > 0 and actual > max_ns:
            failures.append(f"{name}: {actual} ns/iter > {max_ns} ns/iter")
    if missing:
        print("missing benchmark results: " + ", ".join(missing), file=sys.stderr)
        return 1
    if failures:
        print("rust benchmark gate failed:", file=sys.stderr)
        for item in failures:
            print(f"- {item}", file=sys.stderr)
        return 1
    print(f"rust benchmark gate passed: {len(results)} results checked")
    return 0


def parse_results(text: str) -> dict[str, int]:
    results: dict[str, int] = {}
    for match in BENCH_RE.finditer(text):
        results[match.group("name")] = int(match.group("value").replace(",", ""))
    return results


if __name__ == "__main__":
    raise SystemExit(main())
