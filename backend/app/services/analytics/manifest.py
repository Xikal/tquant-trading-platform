from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.analytics.config import analytics_config


def dataset_version(dataset_key: str, generated_at: datetime | None = None) -> str:
    stamp = (generated_at or datetime.utcnow()).strftime("%Y%m%d%H%M%S")
    return f"{dataset_key}_{stamp}"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(manifest: dict[str, Any], *, output_root: str | Path | None = None) -> Path:
    config = analytics_config(output_root)
    config.ensure_dirs()
    version = str(manifest.get("dataset_version") or dataset_version(str(manifest.get("dataset_key") or "dataset")))
    path = config.manifest_dir / f"{version}.json"
    payload = dict(manifest)
    payload["manifest_path"] = str(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    latest = config.manifest_dir / f"{payload.get('dataset_key', 'dataset')}.latest.json"
    latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_manifest(manifest: str | Path, *, output_root: str | Path | None = None) -> dict[str, Any]:
    path = _resolve_manifest_path(manifest, output_root=output_root)
    return json.loads(path.read_text(encoding="utf-8"))


def latest_manifest_path(dataset_key: str = "daily_bars", *, output_root: str | Path | None = None) -> Path | None:
    config = analytics_config(output_root)
    explicit = config.manifest_dir / f"{dataset_key}.latest.json"
    if explicit.exists():
        return explicit
    candidates = sorted(config.manifest_dir.glob(f"{dataset_key}_*.json"))
    return candidates[-1] if candidates else None


def _resolve_manifest_path(manifest: str | Path, *, output_root: str | Path | None = None) -> Path:
    raw = str(manifest)
    if raw == "latest":
        latest = latest_manifest_path(output_root=output_root)
        if latest is None:
            raise FileNotFoundError("未找到 latest daily_bars Manifest。")
        return latest
    path = Path(manifest)
    if path.exists():
        return path
    config = analytics_config(output_root)
    candidate = config.manifest_dir / raw
    if candidate.exists():
        return candidate
    if not raw.endswith(".json"):
        candidate = config.manifest_dir / f"{raw}.json"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Manifest 不存在: {manifest}")
