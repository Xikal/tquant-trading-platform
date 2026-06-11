from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.cloud_resource_gate_observation.constants import TRADING_DAY_CHECKPOINTS


def load_reports(paths: list[Path]) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for path in paths:
        report = json.loads(path.read_text(encoding="utf-8"))
        report.setdefault("source_file", str(path))
        reports.append(report)
    return reports


def checkpoint_label(report: dict[str, Any]) -> str:
    value = report.get("checkpoint", {}).get("label")
    if value:
        return str(value)
    return str(report.get("host", {}).get("date") or report.get("generated_at") or "unknown")


def _max_numeric(values: list[Any]) -> float | None:
    numbers = [float(value) for value in values if isinstance(value, (int, float))]
    return max(numbers) if numbers else None


def _max_container_memory_pct(reports: list[dict[str, Any]], name_part: str) -> float | None:
    values: list[Any] = []
    for report in reports:
        for row in report.get("docker", {}).get("stats", {}).get("rows", []):
            if name_part in str(row.get("name", "")):
                values.append(row.get("memory_pct"))
    return _max_numeric(values)


def summarize_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    observed_labels = [checkpoint_label(report) for report in reports]
    required_labels = [label for label, _description in TRADING_DAY_CHECKPOINTS]
    missing_labels = [label for label in required_labels if label not in observed_labels]
    blockers = sorted(
        {
            blocker
            for report in reports
            for blocker in report.get("evaluation", {}).get("d5_gate", {}).get("blockers", [])
            if blocker != "full_trading_day_observation_incomplete"
        }
    )
    warnings = sorted(
        {
            warning
            for report in reports
            for warning in report.get("evaluation", {}).get("warnings", [])
        }
    )
    available_values = [
        report.get("host", {}).get("memory", {}).get("mem", {}).get("available_mb")
        for report in reports
    ]
    swap_values = [
        report.get("host", {}).get("memory", {}).get("swap", {}).get("used_pct")
        for report in reports
    ]
    root_values = [
        report.get("host", {}).get("root", {}).get("used_pct")
        for report in reports
    ]
    return {
        "checkpoint_count": len(reports),
        "required_checkpoints": required_labels,
        "observed_checkpoints": observed_labels,
        "missing_checkpoints": missing_labels,
        "full_trading_day_complete": not missing_labels,
        "d5_ready": bool(reports) and not missing_labels and not blockers,
        "d5_blockers": (["full_trading_day_observation_incomplete"] if missing_labels else []) + blockers,
        "warnings": warnings,
        "min_memory_available_mb": min(
            float(value) for value in available_values if isinstance(value, (int, float))
        )
        if any(isinstance(value, (int, float)) for value in available_values)
        else None,
        "max_swap_used_pct": _max_numeric(swap_values),
        "max_root_used_pct": _max_numeric(root_values),
        "max_runtime_worker_memory_pct": _max_container_memory_pct(reports, "runtime-worker"),
        "max_runtime_scheduler_memory_pct": _max_container_memory_pct(reports, "runtime-scheduler"),
        "max_mysql_memory_pct": _max_container_memory_pct(reports, "mysql"),
    }


def render_summary_markdown(summary: dict[str, Any], reports: list[dict[str, Any]]) -> str:
    lines = [
        "# Cloud Resource Trading Day Gate Summary",
        "",
        f"- D5 ready: `{str(summary['d5_ready']).lower()}`",
        f"- Full trading day complete: `{str(summary['full_trading_day_complete']).lower()}`",
        f"- D5 blockers: {', '.join(summary['d5_blockers']) or 'none'}",
        f"- Warnings: {', '.join(summary['warnings']) or 'none'}",
        "",
        "## Coverage",
        "",
        "| Checkpoint | Required | Observed |",
        "| --- | --- | --- |",
    ]
    observed = set(summary["observed_checkpoints"])
    for label, description in TRADING_DAY_CHECKPOINTS:
        lines.append(
            f"| `{label}` | {description} | {'yes' if label in observed else 'no'} |"
        )
    lines.extend(
        [
            "",
            "## Resource Envelope",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
            f"| Min memory available MB | {summary['min_memory_available_mb'] if summary['min_memory_available_mb'] is not None else 'unknown'} |",
            f"| Max swap used percent | {summary['max_swap_used_pct'] if summary['max_swap_used_pct'] is not None else 'unknown'} |",
            f"| Max root used percent | {summary['max_root_used_pct'] if summary['max_root_used_pct'] is not None else 'unknown'} |",
            f"| Max runtime-worker memory percent | {summary['max_runtime_worker_memory_pct'] if summary['max_runtime_worker_memory_pct'] is not None else 'unknown'} |",
            f"| Max runtime-scheduler memory percent | {summary['max_runtime_scheduler_memory_pct'] if summary['max_runtime_scheduler_memory_pct'] is not None else 'unknown'} |",
            f"| Max MySQL memory percent | {summary['max_mysql_memory_pct'] if summary['max_mysql_memory_pct'] is not None else 'unknown'} |",
            "",
            "## Snapshots",
            "",
            "| Checkpoint | Generated at | Status | D5 blockers | Warnings |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for report in reports:
        evaluation = report.get("evaluation", {})
        gate = evaluation.get("d5_gate", {})
        lines.append(
            "| `{}` | `{}` | `{}` | {} | {} |".format(
                checkpoint_label(report),
                report.get("generated_at", ""),
                evaluation.get("status", "unknown"),
                ", ".join(gate.get("blockers", [])) or "none",
                ", ".join(evaluation.get("warnings", [])) or "none",
            )
        )
    lines.extend(
        [
            "",
            "## Operations Not Executed",
            "",
            "- This summary reads local JSON snapshots only.",
            "- No .env change.",
            "- No Docker restart/recreate/remove.",
            "- No scheduler stop.",
            "- No DB write.",
            "- No nginx/systemd change.",
            "- No Docker cleanup.",
            "- No deployment or cutover.",
            "",
        ]
    )
    return "\n".join(lines)
