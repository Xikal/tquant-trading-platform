#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKUP_ROOT = Path("/etc/tquant-resource-backups")


@dataclass(frozen=True)
class InstallItem:
    name: str
    source: Path
    target: Path
    mode: int = 0o644
    merge_json: bool = False


INSTALL_ITEMS = (
    InstallItem(
        "docker_daemon",
        ROOT_DIR / "deploy" / "docker" / "daemon-resource.json",
        Path("/etc/docker/daemon.json"),
        merge_json=True,
    ),
    InstallItem(
        "journald_dropin",
        ROOT_DIR / "deploy" / "systemd" / "journald-resource.conf",
        Path("/etc/systemd/journald.conf.d/tquant-resource.conf"),
    ),
    InstallItem(
        "buildkit",
        ROOT_DIR / "deploy" / "buildkit" / "buildkitd-resource.toml",
        Path("/etc/buildkit/buildkitd.toml"),
    ),
    InstallItem(
        "sysctl_swappiness",
        ROOT_DIR / "deploy" / "sysctl" / "tquant-swappiness.conf",
        Path("/etc/sysctl.d/99-tquant-swappiness.conf"),
    ),
    InstallItem(
        "mysql_slow_logrotate",
        ROOT_DIR / "deploy" / "mysql" / "mysql-slow-logrotate.conf",
        Path("/etc/logrotate.d/tquant-mysql-slow-log"),
    ),
)


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def run_command(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def desired_content(item: InstallItem) -> str:
    source_text = read_text(item.source)
    if not item.merge_json or not item.target.exists():
        return source_text

    existing = json.loads(item.target.read_text(encoding="utf-8") or "{}")
    desired = json.loads(source_text)
    if not isinstance(existing, dict) or not isinstance(desired, dict):
        raise ValueError(f"{item.target} must contain a JSON object")
    merged = {**existing, **desired}
    if "log-opts" in existing or "log-opts" in desired:
        merged["log-opts"] = {
            **existing.get("log-opts", {}),
            **desired.get("log-opts", {}),
        }
    return json.dumps(merged, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def backup_existing(target: Path, backup_dir: Path) -> Path | None:
    if not target.exists():
        return None
    backup_path = backup_dir / target.relative_to("/").as_posix()
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, backup_path)
    return backup_path


def install_item(item: InstallItem, apply: bool, backup_dir: Path) -> dict[str, Any]:
    content = desired_content(item)
    current = item.target.read_text(encoding="utf-8") if item.target.exists() else None
    changed = current != content
    result: dict[str, Any] = {
        "name": item.name,
        "source": str(item.source),
        "target": str(item.target),
        "changed": changed,
        "backup": None,
        "applied": False,
    }
    if not changed or not apply:
        return result

    backup = backup_existing(item.target, backup_dir)
    item.target.parent.mkdir(parents=True, exist_ok=True)
    item.target.write_text(content, encoding="utf-8")
    item.target.chmod(item.mode)
    result["backup"] = str(backup) if backup else None
    result["applied"] = True
    return result


def validate_templates() -> None:
    for item in INSTALL_ITEMS:
        if not item.source.exists():
            raise FileNotFoundError(item.source)
    docker = json.loads((ROOT_DIR / "deploy" / "docker" / "daemon-resource.json").read_text(encoding="utf-8"))
    assert docker["log-opts"]["max-size"] == "50m"
    assert docker["log-opts"]["max-file"] == "3"
    buildkit = (ROOT_DIR / "deploy" / "buildkit" / "buildkitd-resource.toml").read_text(encoding="utf-8")
    assert 'maxUsedSpace = "2GB"' in buildkit
    swappiness = (ROOT_DIR / "deploy" / "sysctl" / "tquant-swappiness.conf").read_text(encoding="utf-8")
    assert "vm.swappiness=10" in swappiness
    slow_logrotate = (ROOT_DIR / "deploy" / "mysql" / "mysql-slow-logrotate.conf").read_text(encoding="utf-8")
    assert "copytruncate" in slow_logrotate


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install bounded platform resource configs. Defaults to dry-run and never prunes data."
    )
    parser.add_argument("--apply", action="store_true", help="Write configs after backing up existing files.")
    parser.add_argument("--backup-root", type=Path, default=BACKUP_ROOT)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--restart-hints", action="store_true", help="Print restart commands after apply.")
    args = parser.parse_args()

    validate_templates()
    backup_dir = args.backup_root / timestamp()
    results = [install_item(item, args.apply, backup_dir) for item in INSTALL_ITEMS]
    commands = []
    if args.apply:
        commands = [
            "sudo systemctl restart docker",
            "sudo systemctl restart systemd-journald",
            "sudo systemctl restart buildkit || true",
            "sudo sysctl --system",
            "sudo docker compose -f docker-compose.mysql.yml up -d mysql",
            "sudo logrotate -d /etc/logrotate.d/tquant-mysql-slow-log",
        ]
    payload = {
        "dry_run": not args.apply,
        "backup_dir": str(backup_dir),
        "items": results,
        "restart_hints": commands,
    }
    output = json.dumps(payload, ensure_ascii=False, indent=2)
    print(output)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(output + "\n", encoding="utf-8")
    if args.restart_hints and commands:
        for command in commands:
            print(command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
