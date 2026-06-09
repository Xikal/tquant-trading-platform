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


DEFAULT_WARNINGS = {
    "root_used_pct": 70,
    "root_blocking_pct": 80,
    "swap_used_pct": 50,
    "slow_log_bytes": 512 * 1024 * 1024,
    "docker_build_cache_bytes": 2 * 1024 * 1024 * 1024,
    "binlog_expire_seconds": 259200,
    "max_binlog_size_bytes": 256 * 1024 * 1024,
    "deploy_backup_count": 3,
    "mysql_backup_min_count": 1,
}

RESOURCE_CONFIG_PATHS = {
    "docker_daemon": Path("/etc/docker/daemon.json"),
    "journald": Path("/etc/systemd/journald.conf"),
    "journald_dropin": Path("/etc/systemd/journald.conf.d/tquant-resource.conf"),
    "buildkit": Path("/etc/buildkit/buildkitd.toml"),
    "sysctl_swappiness": Path("/etc/sysctl.d/99-tquant-swappiness.conf"),
    "mysql_slow_logrotate": Path("/etc/logrotate.d/tquant-mysql-slow-log"),
}


@dataclass(frozen=True)
class CommandResult:
    command: str
    returncode: int
    stdout: str
    stderr: str


def run_command(command: list[str], timeout: int = 20) -> CommandResult:
    try:
        completed = subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        return CommandResult(" ".join(command), 127, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            " ".join(command),
            124,
            exc.stdout or "",
            exc.stderr or "command timed out",
        )
    return CommandResult(
        " ".join(command),
        completed.returncode,
        completed.stdout,
        completed.stderr,
    )


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


def parse_df(stdout: str) -> dict[str, Any]:
    lines = [line.split() for line in stdout.splitlines() if line.strip()]
    if len(lines) < 2:
        return {}
    row = lines[-1]
    if len(row) < 6:
        return {}
    return {
        "filesystem": row[0],
        "size": row[1],
        "used": row[2],
        "available": row[3],
        "used_pct": int(row[4].rstrip("%")),
        "mount": row[5],
    }


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
            result[label] = {
                "total_mb": total,
                "used_mb": used,
                "free_mb": int(parts[3]),
                "used_pct": round((used / total) * 100, 2) if total else 0,
            }
            if len(parts) >= 7 and label == "mem":
                result[label]["available_mb"] = int(parts[6])
    return result


def parse_docker_system_df(stdout: str) -> dict[str, Any]:
    docker: dict[str, Any] = {}
    for line in stdout.splitlines():
        if not line.strip() or line.startswith("TYPE"):
            continue
        parts = re.split(r"\s{2,}", line.strip())
        if len(parts) < 5:
            continue
        key = parts[0].lower().replace(" ", "_")
        docker[key] = {
            "total": parts[1],
            "active": parts[2],
            "size": parts[3],
            "reclaimable": parts[4],
            "size_bytes": parse_size_to_bytes(parts[3]),
        }
    return docker


def parse_swappiness(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    try:
        value = int(text.splitlines()[-1].strip())
    except (IndexError, ValueError):
        return {}
    return {"value": value, "recommended_value": 10, "ok": value <= 10}


def parse_docker_stats(stdout: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    total_memory_bytes = 0
    for line in stdout.splitlines():
        raw = line.strip()
        if not raw or raw.startswith(("NAME\t", "NAMES\t")):
            continue
        parts = raw.split("\t")
        if len(parts) < 4:
            continue
        memory_usage = parts[2]
        used_text = memory_usage.split("/", 1)[0].strip()
        used_bytes = parse_size_to_bytes(used_text)
        if isinstance(used_bytes, int):
            total_memory_bytes += used_bytes
        rows.append(
            {
                "name": parts[0],
                "cpu_percent": parts[1],
                "memory_usage": memory_usage,
                "memory_used_bytes": used_bytes,
                "memory_percent": parts[3],
            }
        )
    return {
        "count": len(rows),
        "total_memory_bytes": total_memory_bytes,
        "rows": rows,
    }


def parse_separated_stack(stdout: str) -> dict[str, Any]:
    expected = {"tquant-frontend-web", "tquant-backend-api", "tquant-separated-gateway"}
    rows = []
    running = set()
    for line in stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 2 or parts[0] == "NAME":
            continue
        name = parts[0].strip()
        status = parts[1].strip()
        rows.append({"name": name, "status": status})
        if name in expected and status.lower().startswith(("up", "running", "healthy")):
            running.add(name)
    return {
        "expected": sorted(expected),
        "running": sorted(running),
        "running_count": len(running),
        "all_running": running == expected,
        "rows": rows,
    }


def parse_app_worker_count(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    env_match = re.search(r"APP_WORKERS=([0-9]+)", text)
    direct_match = re.search(r"(?:^|\s)-w\s+\\?\"?([0-9]+)\\?\"?", text)
    fallback_match = re.search(r"\$\{APP_WORKERS:-([0-9]+)\}", text)
    env_value = int(env_match.group(1)) if env_match else None
    if env_value is not None:
        worker_count = env_value
    elif direct_match:
        worker_count = int(direct_match.group(1))
    elif fallback_match:
        worker_count = int(fallback_match.group(1))
    else:
        worker_count = None
    return {
        "command": text,
        "gunicorn_workers": worker_count,
        "app_workers_env": env_value,
        "default_ok": worker_count in (None, 1) and env_value in (None, 1),
    }


def parse_journal_usage(stdout: str) -> dict[str, Any]:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?\s*[KMGTPE]?)", stdout, re.I)
    if not match:
        return {}
    value = match.group(1)
    return {"usage": value, "usage_bytes": parse_size_to_bytes(value)}


def parse_du(stdout: str) -> dict[str, Any]:
    rows = []
    for line in stdout.splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            rows.append({"size": parts[0], "path": parts[1], "size_bytes": parse_size_to_bytes(parts[0])})
    return {"rows": rows}


def parse_mysql_variables(stdout: str) -> dict[str, Any]:
    variables: dict[str, Any] = {}
    for line in stdout.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2:
            key = parts[0][2:] if parts[0].startswith("@@") else parts[0]
            value = parts[-1]
            if key in {"binlog_expire_logs_seconds", "max_binlog_size"}:
                variables[key] = int(value) if value.isdigit() else value
    return variables


def parse_mysql_binary_logs(stdout: str) -> dict[str, Any]:
    logs = []
    for line in stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1].isdigit() and not parts[0].lower().startswith("log_name"):
            logs.append({"name": parts[0], "size_bytes": int(parts[1])})
    return {
        "count": len(logs),
        "total_bytes": sum(row["size_bytes"] for row in logs),
        "logs": logs,
    }


def parse_config_presence(stdout: str) -> dict[str, Any]:
    configs: dict[str, Any] = {}
    for line in stdout.splitlines():
        parts = line.strip().split(maxsplit=2)
        if len(parts) >= 2:
            key = parts[0]
            status = parts[1]
            configs[key] = {
                "present": status == "present",
                "path": parts[2] if len(parts) == 3 else "",
            }
    return configs


def parse_deploy_backups(stdout: str) -> dict[str, Any]:
    rows = []
    for line in stdout.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) < 3:
            continue
        size_bytes = parse_size_to_bytes(parts[0])
        rows.append({"size": parts[0], "mtime": parts[1], "path": parts[2], "size_bytes": size_bytes})
    return {
        "count": len(rows),
        "total_bytes": sum(int(row["size_bytes"] or 0) for row in rows),
        "rows": rows,
    }


def parse_mysql_backups(stdout: str) -> dict[str, Any]:
    rows = []
    for line in stdout.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) < 3:
            continue
        size_bytes = parse_size_to_bytes(parts[0])
        rows.append({"size": parts[0], "mtime": parts[1], "path": parts[2], "size_bytes": size_bytes})
    latest = rows[0] if rows else None
    return {
        "count": len(rows),
        "total_bytes": sum(int(row["size_bytes"] or 0) for row in rows),
        "latest": latest,
        "rows": rows,
    }


def evaluate(report: dict[str, Any], thresholds: dict[str, int]) -> dict[str, Any]:
    warnings: list[str] = []
    blocking: list[str] = []

    root_pct = report.get("root", {}).get("used_pct")
    if isinstance(root_pct, int):
        if root_pct >= thresholds["root_blocking_pct"]:
            blocking.append(f"root_used_pct={root_pct}")
        elif root_pct >= thresholds["root_used_pct"]:
            warnings.append(f"root_used_pct={root_pct}")

    swap_pct = report.get("memory", {}).get("swap", {}).get("used_pct")
    if isinstance(swap_pct, (int, float)) and swap_pct >= thresholds["swap_used_pct"]:
        warnings.append(f"swap_used_pct={swap_pct}")

    slow_log = report.get("mysql", {}).get("slow_log", {})
    slow_log_bytes = slow_log.get("size_bytes") if isinstance(slow_log, dict) else None
    if slow_log_bytes is None and isinstance(slow_log, dict):
        slow_log_bytes = parse_size_to_bytes(str(slow_log.get("size", "")))
    if isinstance(slow_log_bytes, int) and slow_log_bytes >= thresholds["slow_log_bytes"]:
        warnings.append(f"mysql_slow_log_bytes={slow_log_bytes}")

    build_cache = report.get("docker", {}).get("build_cache", {})
    build_cache_bytes = build_cache.get("size_bytes") if isinstance(build_cache, dict) else None
    if build_cache_bytes is None and isinstance(build_cache, dict):
        build_cache_bytes = parse_size_to_bytes(str(build_cache.get("size", "")))
    if isinstance(build_cache_bytes, int) and build_cache_bytes >= thresholds["docker_build_cache_bytes"]:
        warnings.append(f"docker_build_cache_bytes={build_cache_bytes}")

    swappiness = report.get("swappiness", {}).get("value")
    if isinstance(swappiness, int) and swappiness > 10:
        warnings.append(f"swappiness={swappiness}")

    separated_stack = report.get("separated_stack", {})
    if isinstance(separated_stack, dict) and separated_stack.get("running_count"):
        warnings.append(f"separated_stack_running={separated_stack.get('running_count')}")

    app_workers = report.get("app_workers", {}).get("gunicorn_workers")
    if isinstance(app_workers, int) and app_workers > 1:
        warnings.append(f"app_gunicorn_workers={app_workers}")

    expire_seconds = report.get("mysql", {}).get("variables", {}).get("binlog_expire_logs_seconds")
    if isinstance(expire_seconds, int) and expire_seconds > thresholds["binlog_expire_seconds"]:
        warnings.append(f"binlog_expire_logs_seconds={expire_seconds}")
    max_binlog_size = report.get("mysql", {}).get("variables", {}).get("max_binlog_size")
    if isinstance(max_binlog_size, int) and max_binlog_size > thresholds["max_binlog_size_bytes"]:
        warnings.append(f"max_binlog_size={max_binlog_size}")

    deploy_backups = report.get("deploy_backups", {})
    deploy_backup_count = deploy_backups.get("count") if isinstance(deploy_backups, dict) else None
    if isinstance(deploy_backup_count, int) and deploy_backup_count > thresholds["deploy_backup_count"]:
        warnings.append(f"deploy_backup_count={deploy_backup_count}")

    configs = report.get("resource_configs", {})
    mysql_backups = report.get("mysql_backups", {})
    mysql_backup_count = mysql_backups.get("count") if isinstance(mysql_backups, dict) else None
    if isinstance(mysql_backup_count, int) and mysql_backup_count < thresholds["mysql_backup_min_count"]:
        warnings.append(f"mysql_backup_count={mysql_backup_count}")

    for name in (
        "docker_daemon",
        "journald_dropin",
        "buildkit",
        "mysql_compose_resource_config",
        "mysql_slow_logrotate",
    ):
        config = configs.get(name)
        if isinstance(config, dict) and config.get("present") is False:
            warnings.append(f"resource_config_missing={name}")

    commands = report.get("commands", {})
    for name in (
        "docker_system_df",
        "docker_stats",
        "swappiness",
        "separated_stack",
        "app_workers",
        "journal",
        "mysql_volume",
        "mysql_slow_log",
        "mysql_variables",
        "resource_configs",
        "deploy_backups",
        "mysql_backups",
    ):
        result = commands.get(name)
        if isinstance(result, dict) and result.get("returncode") not in (0, None):
            warnings.append(f"collector_{name}_unavailable")
    source = report.get("source", {})
    if not commands and (not source.get("fixture") or source.get("local")):
        warnings.append("collector_command_evidence_missing")

    return {
        "ok": not blocking,
        "status": "blocking" if blocking else ("warning" if warnings else "ok"),
        "warnings": warnings,
        "blocking": blocking,
    }


def collect_from_commands(commands: dict[str, CommandResult]) -> dict[str, Any]:
    mysql_variables = parse_mysql_variables(commands.get("mysql_variables", CommandResult("", 1, "", "")).stdout)
    mysql_logs = parse_mysql_binary_logs(commands.get("mysql_binary_logs", CommandResult("", 1, "", "")).stdout)
    slow_log = parse_du(commands.get("mysql_slow_log", CommandResult("", 1, "", "")).stdout)
    slow_log_row = slow_log["rows"][0] if slow_log["rows"] else {}
    mysql_volume_rows = parse_du(commands.get("mysql_volume", CommandResult("", 1, "", "")).stdout)["rows"]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": parse_df(commands.get("df_root", CommandResult("", 1, "", "")).stdout),
        "memory": parse_free(commands.get("free", CommandResult("", 1, "", "")).stdout),
        "docker": parse_docker_system_df(commands.get("docker_system_df", CommandResult("", 1, "", "")).stdout),
        "docker_stats": parse_docker_stats(commands.get("docker_stats", CommandResult("", 1, "", "")).stdout),
        "swappiness": parse_swappiness(commands.get("swappiness", CommandResult("", 1, "", "")).stdout),
        "separated_stack": parse_separated_stack(
            commands.get("separated_stack", CommandResult("", 1, "", "")).stdout
        ),
        "app_workers": parse_app_worker_count(
            commands.get("app_workers", CommandResult("", 1, "", "")).stdout
        ),
        "journal": parse_journal_usage(commands.get("journal", CommandResult("", 1, "", "")).stdout),
        "mysql": {
            "volume": {"rows": mysql_volume_rows},
            "slow_log": slow_log_row,
            "variables": mysql_variables,
            "binary_logs": mysql_logs,
        },
        "resource_configs": parse_config_presence(
            commands.get("resource_configs", CommandResult("", 1, "", "")).stdout
        ),
        "deploy_backups": parse_deploy_backups(
            commands.get("deploy_backups", CommandResult("", 1, "", "")).stdout
        ),
        "mysql_backups": parse_mysql_backups(
            commands.get("mysql_backups", CommandResult("", 1, "", "")).stdout
        ),
        "commands": {
            name: {
                "command": result.command,
                "returncode": result.returncode,
                "stderr": result.stderr.strip(),
            }
            for name, result in commands.items()
        },
    }


def collect_live(mysql_data_dir: Path) -> dict[str, Any]:
    slow_log = mysql_data_dir / "mysql-slow.log"
    commands = {
        "df_root": run_command(["df", "-h", "/"]),
        "free": run_command(["free", "-m"]),
        "docker_system_df": run_command(["sudo", "docker", "system", "df"]),
        "docker_stats": run_command(
            [
                "sudo",
                "docker",
                "stats",
                "--no-stream",
                "--format",
                "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}",
            ]
        ),
        "swappiness": run_command(["sysctl", "-n", "vm.swappiness"]),
        "separated_stack": run_command(
            [
                "sh",
                "-c",
                "sudo docker ps --format '{{.Names}}\t{{.Status}}' | grep -E '^(tquant-frontend-web|tquant-backend-api|tquant-separated-gateway)\t' || true",
            ]
        ),
        "app_workers": run_command(
            [
                "sh",
                "-c",
                "sudo docker inspect tquant-app-mysql --format '{{json .Config.Cmd}} {{json .Config.Env}}' 2>/dev/null || true",
            ]
        ),
        "journal": run_command(["sudo", "journalctl", "--disk-usage"]),
        "mysql_volume": run_command(["du", "-sh", str(mysql_data_dir)]),
        "mysql_slow_log": run_command(["du", "-sh", str(slow_log)]),
        "mysql_variables": run_command(
            [
                "mysql",
                "-NBe",
                (
                    "SELECT 'binlog_expire_logs_seconds', @@binlog_expire_logs_seconds; "
                    "SELECT 'max_binlog_size', @@max_binlog_size;"
                ),
            ]
        ),
        "mysql_binary_logs": run_command(["mysql", "-e", "SHOW BINARY LOGS;"]),
        "resource_configs": run_command(
            [
                "sh",
                "-c",
                "for entry in "
                + " ".join(f"{key}:{path}" for key, path in RESOURCE_CONFIG_PATHS.items())
                + "; do key=${entry%%:*}; path=${entry#*:}; if test -f \"$path\"; then echo \"$key present $path\"; else echo \"$key missing $path\"; fi; done; "
                "if test -f docker-compose.mysql.yml && grep -q -- '--binlog-expire-logs-seconds=${MYSQL_BINLOG_EXPIRE_LOGS_SECONDS:-259200}' docker-compose.mysql.yml && grep -q -- '--max-binlog-size=${MYSQL_MAX_BINLOG_SIZE:-256M}' docker-compose.mysql.yml; then echo 'mysql_compose_resource_config present docker-compose.mysql.yml'; else echo 'mysql_compose_resource_config missing docker-compose.mysql.yml'; fi",
            ]
        ),
        "deploy_backups": run_command(
            [
                "sh",
                "-c",
                "find /home -maxdepth 1 -type d -name 'gupiao-deploy-backup-*' -printf '%s %T@ %p\\n' 2>/dev/null | sort -k2,2nr",
            ]
        ),
        "mysql_backups": run_command(
            [
                "sh",
                "-c",
                "find /home -path '*/mysql-backups/*.sql.gz' -type f -printf '%s %T@ %p\\n' 2>/dev/null | sort -k2,2nr",
            ]
        ),
    }
    report = collect_from_commands(commands)
    if "binlog_expire_logs_seconds" not in report["mysql"]["variables"]:
        value = commands["mysql_variables"].stdout.strip()
        if value.isdigit():
            report["mysql"]["variables"]["binlog_expire_logs_seconds"] = int(value)
    return report


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def collect_remote(host: str, user: str, ssh_key: Path | None, mysql_data_dir: Path) -> dict[str, Any]:
    remote_script = f"""
set -eu
mysql_data_dir={shell_quote(str(mysql_data_dir))}
slow_log="$mysql_data_dir/mysql-slow.log"
printf '__SECTION__:df_root\\n'
df -h / || true
printf '__SECTION__:free\\n'
free -m || true
printf '__SECTION__:docker_system_df\\n'
sudo docker system df || true
printf '__SECTION__:docker_stats\\n'
sudo docker stats --no-stream --format '{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}' || true
printf '__SECTION__:swappiness\\n'
sysctl -n vm.swappiness || true
printf '__SECTION__:separated_stack\\n'
sudo docker ps --format '{{.Names}}\t{{.Status}}' | grep -E '^(tquant-frontend-web|tquant-backend-api|tquant-separated-gateway)\t' || true
printf '__SECTION__:app_workers\\n'
sudo docker inspect tquant-app-mysql --format '{{json .Config.Cmd}} {{json .Config.Env}}' 2>/dev/null || true
printf '__SECTION__:journal\\n'
sudo journalctl --disk-usage || true
printf '__SECTION__:mysql_volume\\n'
sudo du -sh "$mysql_data_dir" 2>/dev/null || true
printf '__SECTION__:mysql_slow_log\\n'
sudo du -sh "$slow_log" 2>/dev/null || true
printf '__SECTION__:mysql_variables\\n'
if test -f /home/ubuntu/gupiao-upload/.env; then
  set -a
  . /home/ubuntu/gupiao-upload/.env
  set +a
fi
if test -n "${{MYSQL_ROOT_PASSWORD:-}}" && test -f /home/ubuntu/gupiao-upload/docker-compose.mysql.yml; then
  cd /home/ubuntu/gupiao-upload
  sudo docker compose -f docker-compose.mysql.yml exec -T mysql mysql -N -uroot -p"$MYSQL_ROOT_PASSWORD" -e "SELECT 'binlog_expire_logs_seconds', @@binlog_expire_logs_seconds; SELECT 'max_binlog_size', @@max_binlog_size;" 2>/dev/null || true
fi
printf '__SECTION__:mysql_binary_logs\\n'
if test -n "${{MYSQL_ROOT_PASSWORD:-}}" && test -f /home/ubuntu/gupiao-upload/docker-compose.mysql.yml; then
  cd /home/ubuntu/gupiao-upload
  sudo docker compose -f docker-compose.mysql.yml exec -T mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "SHOW BINARY LOGS;" 2>/dev/null || true
fi
printf '__SECTION__:resource_configs\\n'
for entry in {" ".join(f"{key}:{path}" for key, path in RESOURCE_CONFIG_PATHS.items())}; do
  key="${{entry%%:*}}"
  path="${{entry#*:}}"
  if test -f "$path"; then
    echo "$key present $path"
  else
    echo "$key missing $path"
  fi
done
if test -f /home/ubuntu/gupiao-upload/docker-compose.mysql.yml \
  && grep -q -- '--binlog-expire-logs-seconds=${{MYSQL_BINLOG_EXPIRE_LOGS_SECONDS:-259200}}' /home/ubuntu/gupiao-upload/docker-compose.mysql.yml \
  && grep -q -- '--max-binlog-size=${{MYSQL_MAX_BINLOG_SIZE:-256M}}' /home/ubuntu/gupiao-upload/docker-compose.mysql.yml; then
  echo "mysql_compose_resource_config present /home/ubuntu/gupiao-upload/docker-compose.mysql.yml"
else
  echo "mysql_compose_resource_config missing /home/ubuntu/gupiao-upload/docker-compose.mysql.yml"
fi
printf '__SECTION__:deploy_backups\\n'
sudo find /home -maxdepth 1 -type d -name 'gupiao-deploy-backup-*' -printf '%s %T@ %p\\n' 2>/dev/null | sort -k2,2nr || true
printf '__SECTION__:mysql_backups\\n'
sudo find /home -path '*/mysql-backups/*.sql.gz' -type f -printf '%s %T@ %p\\n' 2>/dev/null | sort -k2,2nr || true
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
        name: CommandResult(f"remote:{name}", 0 if output or name in {"deploy_backups", "mysql_backups"} else 1, output, "")
        for name, output in sections.items()
    }
    report = collect_from_commands(commands)
    report["source"] = {"remote_host": host, "remote_user": user}
    report["commands"]["ssh"] = {
        "command": "ssh <redacted>",
        "returncode": result.returncode,
        "stderr": result.stderr.strip(),
    }
    if "binlog_expire_logs_seconds" not in report["mysql"]["variables"]:
        value = commands.get("mysql_variables", CommandResult("", 1, "", "")).stdout.strip()
        if value.isdigit():
            report["mysql"]["variables"]["binlog_expire_logs_seconds"] = int(value)
    return report


def load_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_outputs(report: dict[str, Any], json_output: Path | None, markdown_output: Path | None) -> None:
    if json_output:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if markdown_output:
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(render_markdown(report), encoding="utf-8")


def render_markdown(report: dict[str, Any]) -> str:
    evaluation = report.get("evaluation", {})
    lines = [
        "# 平台资源巡检报告",
        "",
        f"- 生成时间：`{report.get('generated_at', '')}`",
        f"- 状态：`{evaluation.get('status', 'unknown')}`",
        f"- 阻断项：{', '.join(evaluation.get('blocking', [])) or '无'}",
        f"- 警告项：{', '.join(evaluation.get('warnings', [])) or '无'}",
        "",
        "## 核心指标",
        "",
        "| 指标 | 当前值 |",
        "| --- | ---: |",
        f"| 根分区使用率 | {report.get('root', {}).get('used_pct', 'unknown')}% |",
        f"| Swap 使用率 | {report.get('memory', {}).get('swap', {}).get('used_pct', 'unknown')}% |",
        f"| Docker build cache | {report.get('docker', {}).get('build_cache', {}).get('size', 'unknown')} |",
        f"| Docker 常驻容器内存合计 | {report.get('docker_stats', {}).get('total_memory_bytes', 'unknown')} bytes |",
        f"| swappiness | {report.get('swappiness', {}).get('value', 'unknown')} |",
        f"| 分离验证栈运行容器数 | {report.get('separated_stack', {}).get('running_count', 'unknown')} |",
        f"| app Gunicorn workers | {report.get('app_workers', {}).get('gunicorn_workers', 'unknown')} |",
        f"| Journal | {report.get('journal', {}).get('usage', 'unknown')} |",
        f"| MySQL slow log | {report.get('mysql', {}).get('slow_log', {}).get('size', 'unknown')} |",
        f"| binlog 保留秒数 | {report.get('mysql', {}).get('variables', {}).get('binlog_expire_logs_seconds', 'unknown')} |",
        f"| binlog 单文件上限 | {report.get('mysql', {}).get('variables', {}).get('max_binlog_size', 'unknown')} bytes |",
        f"| binlog 数量 | {report.get('mysql', {}).get('binary_logs', {}).get('count', 'unknown')} |",
        f"| binlog 总体积 | {report.get('mysql', {}).get('binary_logs', {}).get('total_bytes', 'unknown')} bytes |",
        f"| 部署归档数量 | {report.get('deploy_backups', {}).get('count', 'unknown')} |",
        f"| 部署归档总体积 | {report.get('deploy_backups', {}).get('total_bytes', 'unknown')} bytes |",
        f"| MySQL 备份数量 | {report.get('mysql_backups', {}).get('count', 'unknown')} |",
        f"| MySQL 备份总体积 | {report.get('mysql_backups', {}).get('total_bytes', 'unknown')} bytes |",
        f"| 最新 MySQL 备份 | {report.get('mysql_backups', {}).get('latest', {}).get('path', 'none') if isinstance(report.get('mysql_backups', {}).get('latest'), dict) else 'none'} |",
        "",
        "## 资源配置状态",
        "",
        "| 配置 | 状态 | 路径 |",
        "| --- | --- | --- |",
    ]
    configs = report.get("resource_configs", {})
    if configs:
        for name in sorted(configs):
            config = configs[name]
            lines.append(
                f"| `{name}` | {'present' if config.get('present') else 'missing'} | `{config.get('path', '')}` |"
            )
    else:
        lines.append("| unknown | unknown | unknown |")
    lines.extend(
        [
            "",
        "## 结论",
        "",
        ]
    )
    if evaluation.get("blocking"):
        lines.append("当前存在 blocking 项，部署 gate 必须停止。")
    elif evaluation.get("warnings"):
        lines.append("当前无 blocking 项，但存在 warning 项，需要进入资源治理队列。")
    else:
        lines.append("当前资源巡检通过。")
    lines.append("")
    return "\n".join(lines)


def parse_thresholds(args: argparse.Namespace) -> dict[str, int]:
    thresholds = dict(DEFAULT_WARNINGS)
    if args.root_warning_pct is not None:
        thresholds["root_used_pct"] = args.root_warning_pct
    if args.root_blocking_pct is not None:
        thresholds["root_blocking_pct"] = args.root_blocking_pct
    return thresholds


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect a read-only platform resource report.")
    parser.add_argument("--fixture", type=Path, help="Read a prebuilt JSON fixture instead of live commands.")
    parser.add_argument("--ssh-host", help="Collect from a remote host over SSH without changing state.")
    parser.add_argument("--ssh-user", default="ubuntu")
    parser.add_argument("--ssh-key", type=Path)
    parser.add_argument(
        "--mysql-data-dir",
        type=Path,
        default=Path("/var/lib/docker/volumes/tquant-mysql_mysql_data/_data"),
    )
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--root-warning-pct", type=int)
    parser.add_argument("--root-blocking-pct", type=int)
    parser.add_argument("--fail-on-blocking", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.fixture:
        report = load_fixture(args.fixture)
        report.setdefault("source", {})["fixture"] = str(args.fixture)
    elif args.ssh_host:
        report = collect_remote(args.ssh_host, args.ssh_user, args.ssh_key, args.mysql_data_dir)
    else:
        report = collect_live(args.mysql_data_dir)
        report.setdefault("source", {})["local"] = True
    thresholds = parse_thresholds(args)
    report["thresholds"] = thresholds
    report["evaluation"] = evaluate(report, thresholds)
    write_outputs(report, args.json_output, args.markdown_output)
    print(json.dumps(report["evaluation"], ensure_ascii=False))
    if args.fail_on_blocking and report["evaluation"]["blocking"]:
        return 42
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
