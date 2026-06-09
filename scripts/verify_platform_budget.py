#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROLE_CONTAINERS = {
    "web": "tquant-app-mysql",
    "runtime_worker": "tquant-runtime-worker-mysql",
    "runtime_scheduler": "tquant-runtime-scheduler-mysql",
    "analytics_worker": "tquant-analytics-worker-mysql",
}
OPTIONAL_CONTAINER_ROLES = {"analytics_worker"}

POOL_ENV_KEYS = (
    "DB_POOL_SIZE",
    "DB_MAX_OVERFLOW",
    "RUNTIME_LOW_PRIORITY_TASKS_PAUSED",
    "RUNTIME_LOW_PRIORITY_TASK_TYPES",
    "RUNTIME_BACKGROUND_ROLE",
    "RUNTIME_BACKGROUND_JOBS_ENABLED",
    "RUNTIME_BACKGROUND_COMPACT_MODE_ENABLED",
    "RUNTIME_STARTUP_CACHE_PREWARM_ENABLED",
    "RUNTIME_STARTUP_HISTORY_PREWARM_ENABLED",
    "RUNTIME_LOW_BUY_FULL_SCAN_INTERVAL_SECONDS",
    "RUNTIME_WATCHLIST_REFRESH_INTERVAL_SECONDS",
    "RUNTIME_MARKET_REGIME_REFRESH_INTERVAL_SECONDS",
    "RUNTIME_QUOTE_CACHE_REFRESH_INTERVAL_SECONDS",
    "RUNTIME_HOURLY_MARKET_SNAPSHOT_INTERVAL_SECONDS",
    "RUNTIME_MATERIALIZATION_REFRESH_INTERVAL_SECONDS",
    "RUNTIME_DAILY_BAR_REFRESH_INTERVAL_SECONDS",
    "RUNTIME_LATEST_DATA_WATCHDOG_INTERVAL_SECONDS",
    "RUNTIME_MARKET_REVIEW_INTERVAL_SECONDS",
    "RUNTIME_AGENT_DAILY_REPORT_INTERVAL_SECONDS",
    "APP_WORKERS",
    "TQUANT_ANALYTICS_ENABLED",
    "TQUANT_DUCKDB_THREADS",
    "BACKTEST_PARQUET_DAILY_BARS_ENABLED",
)
SAFE_COMPOSE_ENV_KEYS = set(POOL_ENV_KEYS) | {
    "DB_POOL_TIMEOUT",
    "DB_POOL_RECYCLE",
}

DEFAULT_THRESHOLDS = {
    "mysql_max_connections": 120,
    "pool_budget": 40,
}


@dataclass(frozen=True)
class CommandResult:
    command: str
    returncode: int
    stdout: str
    stderr: str


def run_command(command: list[str], timeout: int = 30) -> CommandResult:
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        return CommandResult(" ".join(command), 127, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        return CommandResult(" ".join(command), 124, exc.stdout or "", exc.stderr or "command timed out")
    return CommandResult(" ".join(command), completed.returncode, completed.stdout, completed.stderr)


def parse_env_lines(stdout: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            result[key] = value.strip()
    return result


def parse_compose_config(stdout: str) -> dict[str, Any]:
    env: dict[str, dict[str, str]] = {}
    commands: dict[str, str] = {}
    current_service: str | None = None
    in_environment = False
    in_command = False
    for raw_line in stdout.splitlines():
        line = raw_line.rstrip()
        service_match = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if service_match:
            current_service = service_match.group(1)
            env.setdefault(current_service, {})
            in_environment = False
            in_command = False
            continue
        if current_service is None:
            continue
        if line.startswith("    environment:"):
            in_environment = True
            in_command = False
            continue
        if line.startswith("    command:"):
            in_command = True
            in_environment = False
            continue
        if re.match(r"^    [A-Za-z0-9_-]+:", line):
            in_environment = False
            in_command = False
        if in_environment:
            match = re.match(r"^\s{6}([A-Z0-9_]+):\s*(.*)$", line)
            if match:
                env[current_service][match.group(1)] = match.group(2).strip().strip('"')
        if in_command:
            commands[current_service] = (commands.get(current_service, "") + " " + line.strip()).strip()
    safe_env = {
        service: {key: value for key, value in values.items() if key in SAFE_COMPOSE_ENV_KEYS}
        for service, values in env.items()
    }
    return {"service_env": safe_env, "service_commands": commands}


def parse_mysql_status(stdout: str) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for line in stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            value = parts[-1]
            values[parts[0]] = int(value) if value.isdigit() else value
    return values


def pool_int(env: dict[str, str], key: str) -> int:
    value = env.get(key, "0")
    return int(value) if str(value).isdigit() else 0


def evaluate(report: dict[str, Any], thresholds: dict[str, int]) -> dict[str, Any]:
    warnings: list[str] = []
    blocking: list[str] = []

    mysql = report.get("mysql", {})
    max_connections = mysql.get("max_connections")
    if isinstance(max_connections, int) and max_connections > thresholds["mysql_max_connections"]:
        warnings.append(f"mysql_max_connections={max_connections}")

    total_pool_budget = report.get("pool_budget", {}).get("total")
    if isinstance(total_pool_budget, int) and total_pool_budget > thresholds["pool_budget"]:
        warnings.append(f"pool_budget={total_pool_budget}")

    web_env = report.get("roles", {}).get("web", {}).get("env", {})
    if str(web_env.get("RUNTIME_BACKGROUND_JOBS_ENABLED", "")).lower() not in {"false", "0", ""}:
        blocking.append("web_background_jobs_enabled")
    if str(web_env.get("TQUANT_ANALYTICS_ENABLED", "")).lower() not in {"false", "0", ""}:
        blocking.append("web_analytics_enabled")

    for role_name, role in report.get("roles", {}).items():
        env = role.get("env", {})
        if role.get("container_present") is False and role_name in OPTIONAL_CONTAINER_ROLES:
            continue
        if role_name != "web" and "RUNTIME_LOW_PRIORITY_TASKS_PAUSED" not in env:
            warnings.append(f"low_priority_pause_env_missing={role_name}")
        if role.get("container_present") is False:
            warnings.append(f"container_missing={role_name}")

    commands = report.get("commands", {})
    for name in ("compose_config", "mysql_status"):
        command = commands.get(name, {})
        if command.get("returncode") not in (0, None):
            warnings.append(f"collector_{name}_unavailable")

    return {
        "ok": not blocking,
        "status": "blocking" if blocking else ("warning" if warnings else "ok"),
        "warnings": warnings,
        "blocking": blocking,
    }


def build_report(commands: dict[str, CommandResult]) -> dict[str, Any]:
    compose = parse_compose_config(commands.get("compose_config", CommandResult("", 1, "", "")).stdout)
    mysql_status = parse_mysql_status(commands.get("mysql_status", CommandResult("", 1, "", "")).stdout)
    roles: dict[str, Any] = {}
    pool_total = 0
    for role_name, container in ROLE_CONTAINERS.items():
        env = parse_env_lines(commands.get(f"container_env_{role_name}", CommandResult("", 1, "", "")).stdout)
        pool_size = pool_int(env, "DB_POOL_SIZE")
        overflow = pool_int(env, "DB_MAX_OVERFLOW")
        roles[role_name] = {
            "container": container,
            "container_present": bool(env),
            "env": {key: env[key] for key in POOL_ENV_KEYS if key in env},
            "pool_budget": pool_size + overflow,
        }
        pool_total += pool_size + overflow
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mysql": {
            "max_connections": mysql_status.get("max_connections"),
            "threads_connected": mysql_status.get("Threads_connected"),
            "threads_running": mysql_status.get("Threads_running"),
        },
        "pool_budget": {"total": pool_total, "target": DEFAULT_THRESHOLDS["pool_budget"]},
        "roles": roles,
        "compose": compose,
        "commands": {
            name: {
                "command": result.command,
                "returncode": result.returncode,
                "stderr": result.stderr.strip(),
            }
            for name, result in commands.items()
        },
    }


def collect_remote(host: str, user: str, ssh_key: Path | None, project_dir: str) -> dict[str, Any]:
    remote_script = f"""
set -eu
cd {shell_quote(project_dir)}
printf '__SECTION__:compose_config\\n'
sudo docker compose -f docker-compose.mysql.yml config 2>/dev/null || true
printf '__SECTION__:mysql_status\\n'
if test -f .env; then
  set -a
  . ./.env
  set +a
fi
if test -n "${{MYSQL_ROOT_PASSWORD:-}}"; then
  sudo docker compose -f docker-compose.mysql.yml exec -T mysql mysql -N -uroot -p"$MYSQL_ROOT_PASSWORD" -e "SHOW VARIABLES LIKE 'max_connections'; SHOW STATUS LIKE 'Threads_connected'; SHOW STATUS LIKE 'Threads_running';" 2>/dev/null || true
fi
for pair in {' '.join(f'{role}:{container}' for role, container in ROLE_CONTAINERS.items())}; do
  role="${{pair%%:*}}"
  container="${{pair#*:}}"
  printf '__SECTION__:container_env_%s\\n' "$role"
  sudo docker inspect "$container" --format '{{{{range .Config.Env}}}}{{{{println .}}}}{{{{end}}}}' 2>/dev/null || true
done
"""
    command = ["ssh", "-o", "StrictHostKeyChecking=no", f"{user}@{host}", remote_script]
    if ssh_key:
        command[1:1] = ["-i", str(ssh_key)]
    result = run_command(command, timeout=90)
    sections: dict[str, str] = {}
    current: str | None = None
    for line in result.stdout.splitlines():
        if line.startswith("__SECTION__:"):
            current = line.split(":", 1)[1]
            sections[current] = ""
        elif current:
            sections[current] += line + "\n"
    commands = {
        name: CommandResult(f"remote:{name}", 0 if output else 1, output, "")
        for name, output in sections.items()
    }
    report = build_report(commands)
    report["source"] = {"remote_host": host, "remote_user": user, "project_dir": project_dir}
    report["commands"]["ssh"] = {
        "command": "ssh <redacted>",
        "returncode": result.returncode,
        "stderr": result.stderr.strip(),
    }
    return report


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def load_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def render_markdown(report: dict[str, Any]) -> str:
    evaluation = report.get("evaluation", {})
    lines = [
        "# 平台连接池与 Worker 降载复验报告",
        "",
        f"- 生成时间：`{report.get('generated_at', '')}`",
        f"- 状态：`{evaluation.get('status', 'unknown')}`",
        f"- 阻断项：{', '.join(evaluation.get('blocking', [])) or '无'}",
        f"- 警告项：{', '.join(evaluation.get('warnings', [])) or '无'}",
        "",
        "## MySQL 与连接池",
        "",
        "| 指标 | 当前值 |",
        "| --- | ---: |",
        f"| max_connections | {report.get('mysql', {}).get('max_connections', 'unknown')} |",
        f"| Threads_connected | {report.get('mysql', {}).get('threads_connected', 'unknown')} |",
        f"| Threads_running | {report.get('mysql', {}).get('threads_running', 'unknown')} |",
        f"| 应用连接池预算总和 | {report.get('pool_budget', {}).get('total', 'unknown')} |",
        "",
        "## 角色预算",
        "",
        "| 角色 | 容器 | pool budget | low priority paused | background jobs | analytics |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for role_name, role in report.get("roles", {}).items():
        env = role.get("env", {})
        lines.append(
            "| "
            + " | ".join(
                [
                    role_name,
                    role.get("container", ""),
                    str(role.get("pool_budget", "unknown")),
                    str(env.get("RUNTIME_LOW_PRIORITY_TASKS_PAUSED", "n/a")),
                    str(env.get("RUNTIME_BACKGROUND_JOBS_ENABLED", "n/a")),
                    str(env.get("TQUANT_ANALYTICS_ENABLED", "n/a")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## 结论", ""])
    if evaluation.get("blocking"):
        lines.append("存在 blocking 项，不能进入部署或 cutover 验证窗口。")
    elif evaluation.get("warnings"):
        lines.append("无 blocking 项，但仍有 warning，需要继续资源治理或在线复验。")
    else:
        lines.append("连接池预算和 Worker 降载复验通过。")
    lines.append("")
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], json_output: Path | None, markdown_output: Path | None) -> None:
    if json_output:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if markdown_output:
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(render_markdown(report), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only verification for DB pool and worker budget.")
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--ssh-host")
    parser.add_argument("--ssh-user", default="ubuntu")
    parser.add_argument("--ssh-key", type=Path)
    parser.add_argument("--project-dir", default="/home/ubuntu/gupiao-upload")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--fail-on-blocking", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.fixture:
        report = load_fixture(args.fixture)
        report.setdefault("source", {})["fixture"] = str(args.fixture)
    elif args.ssh_host:
        report = collect_remote(args.ssh_host, args.ssh_user, args.ssh_key, args.project_dir)
    else:
        raise SystemExit("--fixture or --ssh-host is required")
    report["thresholds"] = dict(DEFAULT_THRESHOLDS)
    report["evaluation"] = evaluate(report, DEFAULT_THRESHOLDS)
    write_outputs(report, args.json_output, args.markdown_output)
    print(json.dumps(report["evaluation"], ensure_ascii=False))
    if args.fail_on_blocking and report["evaluation"]["blocking"]:
        return 42
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
