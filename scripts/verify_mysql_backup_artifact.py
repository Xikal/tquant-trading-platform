#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_BACKUP_GLOB = "/home/*/mysql-backups/*.sql.gz"
SQL_SIGNATURES = (
    "-- MySQL dump",
    "-- MariaDB dump",
    "CREATE TABLE",
    "INSERT INTO",
    "LOCK TABLES",
)


@dataclass(frozen=True)
class CommandResult:
    command: str
    returncode: int
    stdout: str
    stderr: str


def run_command(command: list[str], timeout: int = 120) -> CommandResult:
    try:
        completed = subprocess.run(command, check=False, text=True, capture_output=True, timeout=timeout)
    except FileNotFoundError as exc:
        return CommandResult(" ".join(command), 127, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        return CommandResult(" ".join(command), 124, exc.stdout or "", exc.stderr or "command timed out")
    return CommandResult(" ".join(command), completed.returncode, completed.stdout, completed.stderr)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_gzip_sample(path: Path, limit: int) -> tuple[bool, str, str]:
    try:
        with gzip.open(path, "rb") as handle:
            sample = handle.read(limit)
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                if not chunk:
                    break
        return True, sample.decode("utf-8", errors="ignore"), ""
    except OSError as exc:
        return False, "", str(exc)


def select_latest_backup(backup_path: Path | None, backup_glob: str) -> Path | None:
    if backup_path:
        return backup_path
    candidates = [path for path in Path("/").glob(backup_glob.lstrip("/")) if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def verify_local_backup(path: Path | None, *, backup_glob: str, sample_bytes: int) -> dict[str, Any]:
    selected = select_latest_backup(path, backup_glob)
    if selected is None:
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": {"mode": "local", "backup_glob": backup_glob},
            "backup": {"present": False},
        }
        report["evaluation"] = evaluate(report)
        return report

    stat = selected.stat() if selected.exists() else None
    gzip_ok, sample, gzip_error = read_gzip_sample(selected, sample_bytes) if selected.exists() else (False, "", "backup_missing")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {"mode": "local", "backup_glob": backup_glob},
        "backup": {
            "present": selected.exists(),
            "path": str(selected),
            "size_bytes": stat.st_size if stat else 0,
            "mtime": stat.st_mtime if stat else None,
            "sha256": sha256_file(selected) if selected.exists() else "",
            "gzip_ok": gzip_ok,
            "gzip_error": gzip_error,
            "sql_signature_ok": sql_signature_ok(sample),
            "sql_signatures": matching_sql_signatures(sample),
            "sample_bytes": len(sample.encode("utf-8", errors="ignore")),
        },
    }
    report["evaluation"] = evaluate(report)
    return report


def collect_remote(
    host: str,
    user: str,
    ssh_key: Path | None,
    *,
    backup_glob: str,
    sample_bytes: int,
) -> dict[str, Any]:
    remote_script = f"""
set -eu
LATEST="$(sudo find /home -path '{backup_glob}' -type f -printf '%s %T@ %p\\n' 2>/dev/null | sort -k2,2nr | head -1 || true)"
if test -z "$LATEST"; then
  echo "__NO_BACKUP__"
  exit 0
fi
SIZE="$(printf '%s\\n' "$LATEST" | awk '{{print $1}}')"
MTIME="$(printf '%s\\n' "$LATEST" | awk '{{print $2}}')"
PATH_VALUE="$(printf '%s\\n' "$LATEST" | cut -d' ' -f3-)"
echo "__BACKUP__ $SIZE $MTIME $PATH_VALUE"
if sudo gzip -t "$PATH_VALUE" >/dev/null 2>&1; then
  echo "__GZIP__ ok"
else
  echo "__GZIP__ fail"
fi
SHA="$(sudo sha256sum "$PATH_VALUE" 2>/dev/null | awk '{{print $1}}' || true)"
echo "__SHA256__ $SHA"
echo "__SAMPLE_BEGIN__"
sudo gzip -cd "$PATH_VALUE" 2>/dev/null | head -c {int(sample_bytes)} || true
printf '\\n__SAMPLE_END__\\n'
"""
    command = ["ssh", "-o", "BatchMode=yes"]
    if ssh_key:
        command.extend(["-i", str(ssh_key)])
    command.extend([f"{user}@{host}", remote_script])
    result = run_command(command, timeout=180)
    report = parse_remote_stdout(result.stdout, backup_glob=backup_glob, sample_bytes=sample_bytes)
    report["source"] = {"mode": "ssh", "host": host, "user": user, "backup_glob": backup_glob}
    report["commands"] = {
        "ssh": {
            "command": result.command,
            "returncode": result.returncode,
            "stderr": result.stderr,
        }
    }
    if result.returncode != 0:
        report.setdefault("backup", {"present": False})
    report["evaluation"] = evaluate(report)
    return report


def parse_remote_stdout(stdout: str, *, backup_glob: str, sample_bytes: int) -> dict[str, Any]:
    backup: dict[str, Any] = {"present": False}
    sample = ""
    in_sample = False
    for line in stdout.splitlines():
        if line == "__NO_BACKUP__":
            backup = {"present": False}
            continue
        if line.startswith("__BACKUP__ "):
            parts = line.split(maxsplit=3)
            if len(parts) == 4:
                backup = {
                    "present": True,
                    "size_bytes": int(parts[1]) if parts[1].isdigit() else 0,
                    "mtime": float(parts[2]) if is_float(parts[2]) else None,
                    "path": parts[3],
                }
            continue
        if line.startswith("__GZIP__ "):
            backup["gzip_ok"] = line.strip().endswith(" ok")
            continue
        if line.startswith("__SHA256__ "):
            backup["sha256"] = line.split(maxsplit=1)[1].strip() if len(line.split(maxsplit=1)) == 2 else ""
            continue
        if line == "__SAMPLE_BEGIN__":
            in_sample = True
            continue
        if line == "__SAMPLE_END__":
            in_sample = False
            continue
        if in_sample:
            sample += line + "\n"

    backup["sql_signature_ok"] = sql_signature_ok(sample)
    backup["sql_signatures"] = matching_sql_signatures(sample)
    backup["sample_bytes"] = min(len(sample.encode("utf-8", errors="ignore")), sample_bytes)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {"mode": "ssh", "backup_glob": backup_glob},
        "backup": backup,
    }


def is_float(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def sql_signature_ok(sample: str) -> bool:
    return bool(matching_sql_signatures(sample))


def matching_sql_signatures(sample: str) -> list[str]:
    return [marker for marker in SQL_SIGNATURES if marker in sample]


def evaluate(report: dict[str, Any]) -> dict[str, Any]:
    backup = report.get("backup") or {}
    blocking: list[str] = []
    warnings: list[str] = []
    if not backup.get("present"):
        blocking.append("mysql_backup_missing")
    if backup.get("present") and int(backup.get("size_bytes") or 0) <= 0:
        blocking.append("mysql_backup_empty")
    if backup.get("present") and backup.get("gzip_ok") is not True:
        blocking.append("mysql_backup_gzip_invalid")
    if backup.get("present") and backup.get("sql_signature_ok") is not True:
        blocking.append("mysql_backup_sql_signature_missing")
    commands = report.get("commands") or {}
    ssh = commands.get("ssh") or {}
    if ssh and ssh.get("returncode") not in (0, None):
        warnings.append("collector_ssh_unavailable")
    return {
        "ok": not blocking,
        "status": "blocking" if blocking else ("warning" if warnings else "ok"),
        "blocking": blocking,
        "warnings": warnings,
    }


def render_markdown(report: dict[str, Any]) -> str:
    backup = report.get("backup") or {}
    evaluation = report.get("evaluation") or {}
    lines = [
        "# MySQL 备份校验报告",
        "",
        f"- 生成时间：`{report.get('generated_at', '')}`",
        f"- 状态：`{evaluation.get('status', '')}`",
        f"- 阻断项：{', '.join(evaluation.get('blocking') or []) or '无'}",
        f"- 警告项：{', '.join(evaluation.get('warnings') or []) or '无'}",
        "",
        "## 备份文件",
        "",
        f"- 路径：`{backup.get('path', 'none')}`",
        f"- 存在：`{bool(backup.get('present'))}`",
        f"- 大小：`{backup.get('size_bytes', 0)}` bytes",
        f"- gzip 完整：`{backup.get('gzip_ok')}`",
        f"- SQL dump 特征：`{backup.get('sql_signature_ok')}`",
        f"- 命中特征：{', '.join(backup.get('sql_signatures') or []) or '无'}",
        f"- sha256：`{backup.get('sha256', '')}`",
        "",
    ]
    if evaluation.get("status") == "ok":
        lines.append("当前 MySQL 备份文件可读、可解压，并命中 SQL dump 特征。")
    else:
        lines.append("当前 MySQL 备份校验未通过，不能作为恢复路径证据。")
    lines.append("")
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], json_output: Path | None, markdown_output: Path | None) -> None:
    if json_output:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if markdown_output:
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(render_markdown(report), encoding="utf-8")


def load_fixture(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    report.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
    report["evaluation"] = evaluate(report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MySQL .sql.gz backup artifact without restoring it.")
    parser.add_argument("--backup-path", type=Path)
    parser.add_argument("--backup-glob", default=DEFAULT_BACKUP_GLOB)
    parser.add_argument("--sample-bytes", type=int, default=65_536)
    parser.add_argument("--ssh-host")
    parser.add_argument("--ssh-user", default="ubuntu")
    parser.add_argument("--ssh-key", type=Path)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--fail-on-blocking", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.fixture:
        report = load_fixture(args.fixture)
    elif args.ssh_host:
        report = collect_remote(
            str(args.ssh_host),
            str(args.ssh_user),
            args.ssh_key,
            backup_glob=str(args.backup_glob),
            sample_bytes=int(args.sample_bytes),
        )
    else:
        report = verify_local_backup(args.backup_path, backup_glob=str(args.backup_glob), sample_bytes=int(args.sample_bytes))
    write_outputs(report, args.json_output, args.markdown_output)
    print(json.dumps(report.get("evaluation") or {}, ensure_ascii=False))
    if args.fail_on_blocking and (report.get("evaluation") or {}).get("status") == "blocking":
        return 42
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
