#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_BUDGETS = {
    "tquant_rust_math_fallback_ratio_bps": 5000,
    "tquant_local_quote_cache_coverage_ratio_bps_min": 9000,
    "tquant_runtime_task_duration_p95_ms": 600000,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Report backend compute acceleration performance budget signals.")
    parser.add_argument("--metrics-file", type=Path, help="Prometheus text or JSON metrics file to inspect.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when a budget is exceeded.")
    args = parser.parse_args()

    metrics = _load_metrics(args.metrics_file) if args.metrics_file else {}
    findings = _findings(metrics)
    payload = {
        "ok": not any(item["status"] == "exceeded" for item in findings) or not args.strict,
        "strict": args.strict,
        "budgets": DEFAULT_BUDGETS,
        "findings": findings,
        "note": "initial optional budget smoke; cloud p95 is reported but not a hard deploy gate unless --strict is set",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if args.strict and not payload["ok"] else 0


def _load_metrics(path: Path) -> dict[str, float]:
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("{"):
        raw = json.loads(text)
        return {str(key): float(value) for key, value in raw.items() if _is_number(value)}
    metrics: dict[str, float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        name = parts[0].split("{", 1)[0]
        try:
            metrics[name] = float(parts[1])
        except ValueError:
            continue
    return metrics


def _findings(metrics: dict[str, float]) -> list[dict[str, Any]]:
    if not metrics:
        return [{"metric": "metrics_input", "status": "not_measured", "message": "no metrics file supplied"}]
    findings: list[dict[str, Any]] = []
    fallback_ratio = metrics.get("tquant_rust_math_fallback_ratio_bps")
    findings.append(_max_budget("tquant_rust_math_fallback_ratio_bps", fallback_ratio, DEFAULT_BUDGETS["tquant_rust_math_fallback_ratio_bps"]))
    coverage_ratio = metrics.get("tquant_local_quote_cache_coverage_ratio_bps")
    findings.append(
        _min_budget(
            "tquant_local_quote_cache_coverage_ratio_bps",
            coverage_ratio,
            DEFAULT_BUDGETS["tquant_local_quote_cache_coverage_ratio_bps_min"],
        )
    )
    runtime_p95 = metrics.get("tquant_runtime_task_duration_p95_ms")
    findings.append(_max_budget("tquant_runtime_task_duration_p95_ms", runtime_p95, DEFAULT_BUDGETS["tquant_runtime_task_duration_p95_ms"]))
    return findings


def _max_budget(metric: str, value: float | None, budget: float) -> dict[str, Any]:
    if value is None:
        return {"metric": metric, "status": "not_measured", "budget": budget}
    return {"metric": metric, "value": value, "budget": budget, "status": "exceeded" if value > budget else "ok"}


def _min_budget(metric: str, value: float | None, budget: float) -> dict[str, Any]:
    if value is None:
        return {"metric": metric, "status": "not_measured", "budget": budget}
    return {"metric": metric, "value": value, "budget": budget, "status": "exceeded" if value < budget else "ok"}


def _is_number(value: object) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


if __name__ == "__main__":
    sys.exit(main())
