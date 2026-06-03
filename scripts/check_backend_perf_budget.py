#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_BUDGETS = {
    "level1": {
        "tquant_rust_math_fallback_ratio_bps": 5000,
    },
    "level2": {
        "tquant_runtime_task_duration_p95_ms": 600000,
        "tquant_response_serialization_ms": 250,
    },
    "level3": {
        "tquant_local_quote_cache_coverage_ratio_bps_min": 9000,
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Report backend compute acceleration performance budget signals.")
    parser.add_argument("--metrics-file", type=Path, help="Prometheus text or JSON metrics file to inspect.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when a budget is exceeded.")
    parser.add_argument(
        "--level",
        choices=["all", "level1", "level2", "level3"],
        default="all",
        help="Budget tier to inspect; only level1 should be used as a normal CI hard gate.",
    )
    args = parser.parse_args()

    metrics = _load_metrics(args.metrics_file) if args.metrics_file else {}
    findings = _findings(metrics, level=args.level)
    blocking_levels = {"level1"} if args.level == "all" else {args.level}
    exceeded = [item for item in findings if item["status"] == "exceeded"]
    strict_exceeded = [item for item in exceeded if str(item.get("level")) in blocking_levels]
    payload = {
        "ok": not strict_exceeded or not args.strict,
        "strict": args.strict,
        "level": args.level,
        "budgets": DEFAULT_BUDGETS,
        "findings": findings,
        "note": "level1 is the CI hard gate; level2 is local service budget; level3 is cloud巡检 and should not block ordinary PRs directly",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if args.strict and not payload["ok"] else 0


def _load_metrics(path: Path) -> dict[str, list[dict[str, Any]]]:
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("{"):
        raw = json.loads(text)
        return {str(key): [{"value": float(value), "labels": {}}] for key, value in raw.items() if _is_number(value)}
    metrics: dict[str, list[dict[str, Any]]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        name, labels = _parse_metric_name(parts[0])
        try:
            metrics.setdefault(name, []).append({"value": float(parts[1]), "labels": labels})
        except ValueError:
            continue
    return metrics


def _findings(metrics: dict[str, list[dict[str, Any]]], *, level: str = "all") -> list[dict[str, Any]]:
    if not metrics:
        return [{"metric": "metrics_input", "status": "not_measured", "message": "no metrics file supplied"}]
    findings: list[dict[str, Any]] = []
    levels = ("level1", "level2", "level3") if level == "all" else (level,)
    if "level1" in levels:
        fallback_ratio = _metric_values(metrics, "tquant_rust_math_fallback_ratio_bps")
        findings.append(
            _max_budget(
                "tquant_rust_math_fallback_ratio_bps",
                fallback_ratio,
                DEFAULT_BUDGETS["level1"]["tquant_rust_math_fallback_ratio_bps"],
                level="level1",
            )
        )
    if "level2" in levels:
        runtime_p95 = _metric_values(metrics, "tquant_runtime_task_duration_p95_ms")
        findings.append(
            _max_budget(
                "tquant_runtime_task_duration_p95_ms",
                runtime_p95,
                DEFAULT_BUDGETS["level2"]["tquant_runtime_task_duration_p95_ms"],
                level="level2",
            )
        )
        serialization_ms = _metric_values(metrics, "tquant_response_serialization_ms")
        findings.append(
            _max_budget(
                "tquant_response_serialization_ms",
                serialization_ms,
                DEFAULT_BUDGETS["level2"]["tquant_response_serialization_ms"],
                level="level2",
            )
        )
    if "level3" in levels:
        coverage_ratio = _metric_values(metrics, "tquant_local_quote_cache_coverage_ratio_bps")
        findings.append(
            _min_budget(
                "tquant_local_quote_cache_coverage_ratio_bps",
                coverage_ratio,
                DEFAULT_BUDGETS["level3"]["tquant_local_quote_cache_coverage_ratio_bps_min"],
                level="level3",
            )
        )
    return findings


def _max_budget(metric: str, values: list[float], budget: float, *, level: str) -> dict[str, Any]:
    if not values:
        return {"level": level, "metric": metric, "status": "not_measured", "budget": budget}
    value = max(values)
    sample_count = len(values)
    return {
        "level": level,
        "metric": metric,
        "value": value,
        "sample_count": sample_count,
        "budget": budget,
        "status": "exceeded" if value > budget else "ok",
    }


def _min_budget(metric: str, values: list[float], budget: float, *, level: str) -> dict[str, Any]:
    if not values:
        return {"level": level, "metric": metric, "status": "not_measured", "budget": budget}
    value = min(values)
    sample_count = len(values)
    return {
        "level": level,
        "metric": metric,
        "value": value,
        "sample_count": sample_count,
        "budget": budget,
        "status": "exceeded" if value < budget else "ok",
    }


def _metric_values(metrics: dict[str, list[dict[str, Any]]], metric: str) -> list[float]:
    values: list[float] = []
    for sample in metrics.get(metric, []):
        labels = sample.get("labels") if isinstance(sample, dict) else {}
        if isinstance(labels, dict) and any(str(value) == "none" for value in labels.values()):
            continue
        value = sample.get("value") if isinstance(sample, dict) else None
        if _is_number(value):
            values.append(float(value))
    return values


def _parse_metric_name(raw: str) -> tuple[str, dict[str, str]]:
    if "{" not in raw or not raw.endswith("}"):
        return raw, {}
    name, label_text = raw.split("{", 1)
    label_text = label_text[:-1]
    labels: dict[str, str] = {}
    for pair in label_text.split(","):
        if "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        labels[key.strip()] = value.strip().strip('"')
    return name, labels


def _is_number(value: object) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


if __name__ == "__main__":
    sys.exit(main())
