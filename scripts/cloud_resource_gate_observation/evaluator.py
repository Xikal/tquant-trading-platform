from __future__ import annotations

from typing import Any

from scripts.cloud_resource_gate_observation.constants import (
    CORE_DUPLICATE_TASK_TYPES,
    CORE_PAGE_PATHS,
    LOW_PRIORITY_TASK_HINTS,
    PROTECTED_API_PATHS,
)


def count_rows(rows: list[dict[str, Any]]) -> int:
    total = 0
    for row in rows:
        try:
            total += int(str(row.get("count", "0")))
        except ValueError:
            continue
    return total


def count_nonblank_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def evaluate(report: dict[str, Any], thresholds: dict[str, float], full_trading_day_complete: bool) -> dict[str, Any]:
    blocking: list[str] = []
    warnings: list[str] = []

    memory = report.get("host", {}).get("memory", {})
    swap_pct = memory.get("swap", {}).get("used_pct") if isinstance(memory, dict) else None
    if isinstance(swap_pct, (int, float)) and swap_pct >= thresholds["swap_warning_pct"]:
        warnings.append(f"swap_used_pct={swap_pct}")

    root_pct = report.get("host", {}).get("root", {}).get("used_pct")
    if isinstance(root_pct, (int, float)) and root_pct >= thresholds["root_warning_pct"]:
        warnings.append(f"root_used_pct={root_pct}")

    compose_ps = report.get("docker", {}).get("compose_ps", {})
    for container in compose_ps.get("missing_expected", []):
        warnings.append(f"expected_container_missing={container}")

    for row in report.get("docker", {}).get("stats", {}).get("rows", []):
        name = str(row.get("name", ""))
        memory_pct = row.get("memory_pct")
        if "runtime-worker" in name and isinstance(memory_pct, (int, float)):
            if memory_pct >= thresholds["worker_memory_blocking_pct"]:
                blocking.append(f"runtime_worker_memory_pct={memory_pct}")
            elif memory_pct >= thresholds["worker_memory_warning_pct"]:
                warnings.append(f"runtime_worker_memory_pct={memory_pct}")

    http_rows = {row.get("path"): row for row in report.get("http", [])}
    readyz = http_rows.get("/readyz", {})
    if readyz.get("status") != 200:
        blocking.append(f"readyz_status={readyz.get('status', 'missing')}")
    for path in CORE_PAGE_PATHS:
        row = http_rows.get(path, {})
        if row.get("status") != 200:
            blocking.append(f"http_status:{path}={row.get('status', 'missing')}")
    for path in PROTECTED_API_PATHS:
        row = http_rows.get(path, {})
        if row.get("status") not in {200, 401, 403}:
            warnings.append(f"protected_api_status:{path}={row.get('status', 'missing')}")

    if report.get("logs", {}).get("oom"):
        blocking.append("kernel_oom_logs_present")
    if report.get("logs", {}).get("worker_signals"):
        warnings.append("runtime_worker_signal_logs_present")
    scheduler_provider_signals = str(report.get("logs", {}).get("scheduler_provider_signals") or "")
    scheduler_provider_signal_lines = count_nonblank_lines(scheduler_provider_signals)
    if scheduler_provider_signal_lines:
        if scheduler_provider_signal_lines >= thresholds["scheduler_provider_warning_blocking_lines"]:
            warnings.append(f"scheduler_provider_warning_lines={scheduler_provider_signal_lines}")
        else:
            warnings.append(f"scheduler_provider_warning_lines_observed={scheduler_provider_signal_lines}")

    queued_total = count_rows(report.get("runtime_tasks", {}).get("nonterminal", []))
    if queued_total >= thresholds["queue_warning_count"]:
        warnings.append(f"runtime_nonterminal_task_count={queued_total}")

    for row in report.get("runtime_tasks", {}).get("recent_summary", []):
        task_type = str(row.get("task_type", ""))
        status = str(row.get("status", ""))
        try:
            count = int(str(row.get("count", "0")))
        except ValueError:
            count = 0
        if (
            task_type in CORE_DUPLICATE_TASK_TYPES
            and status == "succeeded"
            and count > thresholds["duplicate_success_warning_count"]
        ):
            warnings.append(f"duplicate_success_window:{task_type}={count}")
        if any(hint in task_type for hint in LOW_PRIORITY_TASK_HINTS) and status in {"queued", "running"}:
            warnings.append(f"low_priority_task_nonterminal:{task_type}")

    mysql_status = report.get("mysql", {}).get("status", {})
    if not mysql_status:
        warnings.append("mysql_status_unavailable")
    slow_queries = mysql_status.get("Slow_queries")
    if slow_queries not in (None, ""):
        try:
            if int(str(slow_queries)) > 0:
                warnings.append(f"mysql_slow_queries={slow_queries}")
        except ValueError:
            warnings.append(f"mysql_slow_queries={slow_queries}")

    critical_warning_prefixes = (
        "scheduler_provider_warning_lines=",
        "runtime_worker_signal_logs_present",
        "runtime_worker_memory_pct=",
        "runtime_nonterminal_task_count=",
        "duplicate_success_window:",
    )
    d5_blockers = list(blocking)
    if not full_trading_day_complete:
        d5_blockers.append("full_trading_day_observation_incomplete")
    d5_blockers.extend(warning for warning in warnings if warning.startswith(critical_warning_prefixes))

    return {
        "status": "blocking" if blocking else ("warning" if warnings else "ok"),
        "blocking": blocking,
        "warnings": warnings,
        "d5_gate": {
            "ready": not d5_blockers,
            "blockers": d5_blockers,
            "full_trading_day_complete": full_trading_day_complete,
        },
    }
