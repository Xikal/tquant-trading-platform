#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT_DIR / "VERSION.json"


TARGETS = (
    ROOT_DIR / "frontend-next/package.json",
    ROOT_DIR / "frontend-next/package-lock.json",
    ROOT_DIR / "backend/app/services/app_mobile/bootstrap.py",
)


def load_version_config() -> dict[str, object]:
    return json.loads(VERSION_FILE.read_text(encoding="utf-8"))


def save_version_config(config: dict[str, object]) -> None:
    VERSION_FILE.write_text(f"{json.dumps(config, indent=2, ensure_ascii=False)}\n", encoding="utf-8")


def replace_exact(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, flags=re.MULTILINE)
    if count == 0:
        raise RuntimeError(f"Missing expected pattern for {label}: {pattern}")
    return updated


def sync_package_json(path: Path, version: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    path.write_text(f"{json.dumps(data, indent=2, ensure_ascii=False)}\n", encoding="utf-8")


def sync_package_lock(path: Path, version: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    root_package = data.get("packages", {}).get("")
    if isinstance(root_package, dict):
        root_package["version"] = version
    path.write_text(f"{json.dumps(data, indent=2, ensure_ascii=False)}\n", encoding="utf-8")


def sync_bootstrap(path: Path, version: str, min_supported_version: str) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_exact(text, r'^(\s*_app_version = )"[^"]+"$', rf'\1"{version}"', "bootstrap app version")
    text = replace_exact(
        text,
        r'^(\s*_min_supported_version = )"[^"]+"$',
        rf'\1"{min_supported_version}"',
        "bootstrap min supported version",
    )
    path.write_text(text, encoding="utf-8")


def sync_targets(config: dict[str, object]) -> None:
    version = str(config["version"])
    min_supported_version = str(config["min_supported_version"])

    sync_package_json(TARGETS[0], version)
    sync_package_lock(TARGETS[1], version)
    sync_bootstrap(TARGETS[2], version, min_supported_version)


def collect_current_values() -> dict[str, dict[str, object]]:
    package_json = json.loads(TARGETS[0].read_text(encoding="utf-8"))
    package_lock = json.loads(TARGETS[1].read_text(encoding="utf-8"))
    bootstrap_text = TARGETS[2].read_text(encoding="utf-8")

    def match(pattern: str, text: str, label: str) -> str:
        result = re.search(pattern, text, flags=re.MULTILINE)
        if not result:
            raise RuntimeError(f"Missing expected pattern for {label}: {pattern}")
        return result.group(1)

    return {
        "frontend-next/package.json": {
            "version": package_json.get("version"),
        },
        "frontend-next/package-lock.json": {
            "version": package_lock.get("version"),
            "root_version": (package_lock.get("packages") or {}).get("", {}).get("version"),
        },
        "backend/app/services/app_mobile/bootstrap.py": {
            "version": match(r'^\s*_app_version = "([^"]+)"$', bootstrap_text, "bootstrap app version"),
            "min_supported_version": match(
                r'^\s*_min_supported_version = "([^"]+)"$',
                bootstrap_text,
                "bootstrap min supported version",
            ),
        },
    }


def check_targets(config: dict[str, object]) -> int:
    expected_version = str(config["version"])
    expected_min_supported_version = str(config["min_supported_version"])
    current_values = collect_current_values()

    drift_messages: list[str] = []

    if current_values["frontend-next/package.json"]["version"] != expected_version:
        drift_messages.append("frontend-next/package.json version mismatch")
    package_lock_values = current_values["frontend-next/package-lock.json"]
    if package_lock_values["version"] != expected_version:
        drift_messages.append("frontend-next/package-lock.json version mismatch")
    if package_lock_values["root_version"] != expected_version:
        drift_messages.append("frontend-next/package-lock.json root package version mismatch")

    bootstrap_values = current_values["backend/app/services/app_mobile/bootstrap.py"]
    if bootstrap_values["version"] != expected_version:
        drift_messages.append("bootstrap app_version mismatch")
    if bootstrap_values["min_supported_version"] != expected_min_supported_version:
        drift_messages.append("bootstrap min_supported_version mismatch")

    if drift_messages:
        print("version-sync:drift")
        for message in drift_messages:
            print(f"- {message}")
        return 1

    print(
        "version-sync:ok "
        f"version={expected_version} min_supported_version={expected_min_supported_version} "
        "targets=frontend-next,backend-bootstrap"
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync project versions from VERSION.json.")
    parser.add_argument("--check", action="store_true", help="Only verify target files match VERSION.json.")
    parser.add_argument("--set-version", dest="set_version", help="Update VERSION.json with a new marketing version.")
    parser.add_argument("--set-build-number", dest="set_build_number", type=int, help="Update VERSION.json build number.")
    parser.add_argument(
        "--set-min-supported",
        dest="set_min_supported",
        help="Update VERSION.json minimum supported version.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_version_config()

    if args.set_version is not None:
        config["version"] = args.set_version
    if args.set_build_number is not None:
        if args.set_build_number <= 0:
            raise SystemExit("--set-build-number must be greater than 0")
        config["build_number"] = args.set_build_number
    if args.set_min_supported is not None:
        config["min_supported_version"] = args.set_min_supported

    if any(
        value is not None
        for value in (args.set_version, args.set_build_number, args.set_min_supported)
    ):
        save_version_config(config)

    if args.check:
        return check_targets(config)

    sync_targets(config)
    return check_targets(config)


if __name__ == "__main__":
    sys.exit(main())
