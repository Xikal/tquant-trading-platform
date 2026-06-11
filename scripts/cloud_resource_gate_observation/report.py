from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def render_markdown(report: dict[str, Any]) -> str:
    evaluation = report.get("evaluation", {})
    d5_gate = evaluation.get("d5_gate", {})
    lines = [
        "# Cloud Resource Gate Observation",
        "",
        f"- Generated at: `{report.get('generated_at', '')}`",
        f"- Checkpoint: `{report.get('checkpoint', {}).get('label', '') or 'single-snapshot'}`",
        f"- Source: `{report.get('source', {}).get('remote_user', '')}@{report.get('source', {}).get('remote_host', '')}`",
        f"- Evaluation: `{evaluation.get('status', 'unknown')}`",
        f"- D5 embedded scheduler ready: `{str(d5_gate.get('ready', False)).lower()}`",
        f"- D5 blockers: {', '.join(d5_gate.get('blockers', [])) or 'none'}",
        f"- Blocking: {', '.join(evaluation.get('blocking', [])) or 'none'}",
        f"- Warnings: {', '.join(evaluation.get('warnings', [])) or 'none'}",
        "",
        "## Host",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Date | `{report.get('host', {}).get('date', '')}` |",
        f"| Uptime | `{report.get('host', {}).get('uptime', '')}` |",
        f"| Memory available MB | {report.get('host', {}).get('memory', {}).get('mem', {}).get('available_mb', 'unknown')} |",
        f"| Swap used percent | {report.get('host', {}).get('memory', {}).get('swap', {}).get('used_pct', 'unknown')} |",
        f"| Root used percent | {report.get('host', {}).get('root', {}).get('used_pct', 'unknown')} |",
        f"| Root inode used percent | {report.get('host', {}).get('root_inode', {}).get('used_pct', 'unknown')} |",
        "",
        "## Containers",
        "",
        "| Container | CPU | Memory | Memory % |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in report.get("docker", {}).get("stats", {}).get("rows", []):
        lines.append(
            f"| `{row.get('name', '')}` | {row.get('cpu_percent', '')} | {row.get('memory_usage', '')} | {row.get('memory_percent', '')} |"
        )
    lines.extend(
        [
            "",
            "## HTTP",
            "",
            "| Path | Status | Time | Error |",
            "| --- | ---: | ---: | --- |",
        ]
    )
    for row in report.get("http", []):
        lines.append(
            f"| `{row.get('path', '')}` | {row.get('status', 'unknown')} | {row.get('time_total', 'unknown')} | `{row.get('error', '')}` |"
        )
    lines.extend(["", "## MySQL", "", "| Metric | Value |", "| --- | ---: |"])
    for key, value in sorted(report.get("mysql", {}).get("status", {}).items()):
        lines.append(f"| `{key}` | {value} |")
    for key, value in sorted(report.get("mysql", {}).get("variables", {}).items()):
        lines.append(f"| `{key}` | {value} |")
    lines.extend(
        [
            "",
            "## Runtime Tasks",
            "",
            "| Task | Status | Count | Oldest | Latest |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )
    for row in report.get("runtime_tasks", {}).get("recent_summary", []):
        lines.append(
            f"| `{row.get('task_type', '')}` | {row.get('status', '')} | {row.get('count', '')} | {row.get('oldest', '')} | {row.get('latest', '')} |"
        )
    lines.extend(
        [
            "",
            "## Operations Not Executed",
            "",
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


def write_outputs(report: dict[str, Any], json_output: Path | None, markdown_output: Path | None) -> None:
    if json_output:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if markdown_output:
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(render_markdown(report), encoding="utf-8")


def load_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
