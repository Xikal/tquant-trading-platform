#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT_DIR / "VERSION.json"
APP_UPDATE_DIR = ROOT_DIR / "backend" / "data" / "app_updates"
APK_TARGET = APP_UPDATE_DIR / "weis-quant-latest.apk"
MANIFEST_TARGET = APP_UPDATE_DIR / "android.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_version() -> dict:
    return json.loads(VERSION_FILE.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish Android APK and update manifest.")
    parser.add_argument("apk", type=Path, help="Path to the release APK.")
    parser.add_argument("--title", default="发现新版本")
    parser.add_argument("--message", default="建议更新到最新版本。")
    parser.add_argument("--mandatory", action="store_true")
    parser.add_argument("--changelog", action="append", default=[], help="Can be provided multiple times.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    apk_path = args.apk.expanduser().resolve()
    if not apk_path.exists():
        raise SystemExit(f"APK not found: {apk_path}")

    version = load_version()
    APP_UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(apk_path, APK_TARGET)

    manifest = {
        "latest_version_code": int(version["build_number"]),
        "latest_version_name": str(version["version"]),
        "min_supported_version_code": int(version.get("min_supported_build_number") or 1),
        "mandatory": bool(args.mandatory),
        "title": args.title,
        "message": args.message,
        "changelog": args.changelog,
        "apk_sha256": sha256_file(APK_TARGET),
        "apk_size_bytes": APK_TARGET.stat().st_size,
        "published_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    MANIFEST_TARGET.write_text(f"{json.dumps(manifest, indent=2, ensure_ascii=False)}\n", encoding="utf-8")
    print(f"android-update:ok manifest={MANIFEST_TARGET} apk={APK_TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
