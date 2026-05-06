from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.core.config import BACKEND_DIR

APP_UPDATE_DIR = BACKEND_DIR / "data" / "app_updates"
ANDROID_MANIFEST_PATH = APP_UPDATE_DIR / "android.json"
ANDROID_APK_PATH = APP_UPDATE_DIR / "weis-quant-latest.apk"

DEFAULT_ANDROID_MANIFEST = {
    "latest_version_code": 1,
    "latest_version_name": "1.0.0",
    "min_supported_version_code": 1,
    "mandatory": False,
    "title": "当前已是最新版本",
    "message": "当前版本可正常使用。",
    "changelog": [],
    "apk_sha256": "",
    "published_at": "",
}


def load_android_update_manifest() -> dict[str, Any]:
    manifest = dict(DEFAULT_ANDROID_MANIFEST)
    if not ANDROID_MANIFEST_PATH.exists():
        return manifest
    try:
        payload = json.loads(ANDROID_MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return manifest
    if isinstance(payload, dict):
        manifest.update(payload)
    return manifest


def android_apk_size() -> int:
    try:
        return ANDROID_APK_PATH.stat().st_size
    except OSError:
        return 0


def android_apk_sha256() -> str:
    try:
        digest = hashlib.sha256()
        with ANDROID_APK_PATH.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return ""
