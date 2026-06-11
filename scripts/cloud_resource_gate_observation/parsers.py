from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from scripts.cloud_resource_gate_observation.constants import EXPECTED_CONTAINERS


def parse_percent(value: str) -> float | None:
    text = value.strip().rstrip("%")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_size_to_bytes(value: str) -> int | None:
    text = value.strip()
    if not text or text in {"-", "0B"}:
        return 0
    match = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*([KMGTPE]?i?B?|[KMGTPE])?$", text, re.I)
    if not match:
        return None
    number = float(match.group(1))
    unit = (match.group(2) or "B").upper().replace("IB", "I").replace("B", "")
    multiplier = {
        "": 1,
        "K": 1024,
        "KI": 1024,
        "M": 1024**2,
        "MI": 1024**2,
        "G": 1024**3,
        "GI": 1024**3,
        "T": 1024**4,
        "TI": 1024**4,
        "P": 1024**5,
        "PI": 1024**5,
        "E": 1024**6,
        "EI": 1024**6,
    }.get(unit)
    if multiplier is None:
        return None
    return int(number * multiplier)


def parse_free(stdout: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for line in stdout.splitlines():
        parts = line.split()
        if not parts:
            continue
        label = parts[0].rstrip(":").lower()
        if label in {"mem", "swap"} and len(parts) >= 4:
            total = int(parts[1])
            used = int(parts[2])
            row: dict[str, Any] = {
                "total_mb": total,
                "used_mb": used,
                "free_mb": int(parts[3]),
                "used_pct": round((used / total) * 100, 2) if total else 0,
            }
            if label == "mem" and len(parts) >= 7:
                row["available_mb"] = int(parts[6])
            result[label] = row
    return result


def parse_df(stdout: str) -> dict[str, Any]:
    rows = [line.split() for line in stdout.splitlines() if line.strip()]
    if len(rows) < 2 or len(rows[-1]) < 6:
        return {}
    row = rows[-1]
    return {
        "filesystem": row[0],
        "size": row[1],
        "used": row[2],
        "available": row[3],
        "used_pct": int(row[4].rstrip("%")),
        "mount": row[5],
    }


def parse_docker_stats(stdout: str) -> dict[str, Any]:
    rows = []
    for line in stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 4 or parts[0] in {"NAME", "NAMES"}:
            continue
        memory_usage = parts[2]
        used_text = memory_usage.split("/", 1)[0].strip()
        rows.append(
            {
                "name": parts[0],
                "cpu_percent": parts[1],
                "cpu_pct": parse_percent(parts[1]),
                "memory_usage": memory_usage,
                "memory_used_bytes": parse_size_to_bytes(used_text),
                "memory_percent": parts[3],
                "memory_pct": parse_percent(parts[3]),
            }
        )
    return {"count": len(rows), "rows": rows}


def parse_compose_ps(stdout: str) -> dict[str, Any]:
    rows = []
    running = set()
    healthy = set()
    for line in stdout.splitlines():
        raw = line.strip()
        if not raw:
            continue
        parts = raw.split("\t")
        name = parts[0]
        status = parts[1] if len(parts) > 1 else ""
        row = {"name": name, "status": status}
        rows.append(row)
        lowered = status.lower()
        if lowered.startswith(("up", "running")):
            running.add(name)
        if "healthy" in lowered:
            healthy.add(name)
    missing = sorted(EXPECTED_CONTAINERS - {row["name"] for row in rows})
    return {
        "rows": rows,
        "running": sorted(running),
        "healthy": sorted(healthy),
        "missing_expected": missing,
    }


def parse_http(stdout: str) -> list[dict[str, Any]]:
    rows = []
    for line in stdout.splitlines():
        parts = line.split("\t", 3)
        if len(parts) < 3:
            continue
        path, returncode, payload = parts[0], parts[1], parts[2]
        code = None
        time_total = None
        error = ""
        payload_parts = payload.split()
        if payload_parts:
            try:
                code = int(payload_parts[0])
            except ValueError:
                error = payload
        if len(payload_parts) >= 2:
            try:
                time_total = float(payload_parts[1])
            except ValueError:
                error = payload
        rows.append(
            {
                "path": path,
                "returncode": int(returncode) if returncode.isdigit() else returncode,
                "status": code,
                "time_total": time_total,
                "error": error,
            }
        )
    return rows


def parse_mysql_kv(stdout: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            values[parts[0]] = parts[1]
        else:
            parts = line.split()
            if len(parts) >= 2:
                values[parts[0]] = parts[1]
    return values


def parse_mysql_rows(stdout: str, columns: tuple[str, ...]) -> list[dict[str, Any]]:
    rows = []
    for line in stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != len(columns):
            parts = line.split()
        if len(parts) < len(columns):
            continue
        rows.append({column: parts[index] for index, column in enumerate(columns)})
    return rows


def collect_from_sections(sections: dict[str, str]) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host": {
            "date": sections.get("date", "").strip(),
            "uptime": sections.get("uptime", "").strip(),
            "memory": parse_free(sections.get("free", "")),
            "root": parse_df(sections.get("df_root", "")),
            "root_inode": parse_df(sections.get("df_inode_root", "")),
        },
        "docker": {
            "compose_ps": parse_compose_ps(sections.get("compose_ps", "")),
            "stats": parse_docker_stats(sections.get("docker_stats", "")),
            "system_df": sections.get("docker_system_df", "").strip(),
        },
        "http": parse_http(sections.get("http", "")),
        "mysql": {
            "status": parse_mysql_kv(sections.get("mysql_status", "")),
            "variables": parse_mysql_kv(sections.get("mysql_variables", "")),
            "table_space": parse_mysql_rows(
                sections.get("mysql_table_space", ""),
                ("table_schema", "mb"),
            ),
        },
        "runtime_tasks": {
            "recent_summary": parse_mysql_rows(
                sections.get("task_summary", ""),
                ("task_type", "status", "count", "oldest", "latest"),
            ),
            "nonterminal": parse_mysql_rows(
                sections.get("task_nonterminal", ""),
                ("status", "task_type", "priority", "count", "oldest", "latest"),
            ),
            "heartbeats": parse_mysql_rows(
                sections.get("heartbeats", ""),
                ("key", "updated_at", "value_prefix"),
            ),
        },
        "logs": {
            "oom": sections.get("oom_logs", "").strip(),
            "worker_signals": sections.get("worker_logs", "").strip(),
            "scheduler_provider_signals": sections.get("scheduler_logs", "").strip(),
        },
        "raw_sections_present": sorted(sections),
    }
