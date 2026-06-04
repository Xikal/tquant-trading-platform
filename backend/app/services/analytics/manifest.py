from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
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
    payload = _normalize_lifecycle_payload(manifest, version=version)
    payload["manifest_path"] = str(path)
    latest = config.manifest_dir / f"{payload.get('dataset_key', 'dataset')}.latest.json"
    previous = _load_previous_latest(latest)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    _mark_previous_superseded(previous, superseded_by=str(payload["manifest_id"]))
    return path


def load_manifest(manifest: str | Path, *, output_root: str | Path | None = None) -> dict[str, Any]:
    path = _resolve_manifest_path(manifest, output_root=output_root)
    payload = json.loads(path.read_text(encoding="utf-8"))
    version = str(payload.get("dataset_version") or path.stem)
    return _normalize_lifecycle_payload(payload, version=version)


def latest_manifest_path(dataset_key: str = "daily_bars", *, output_root: str | Path | None = None) -> Path | None:
    config = analytics_config(output_root)
    explicit = config.manifest_dir / f"{dataset_key}.latest.json"
    if explicit.exists():
        return explicit
    candidates = sorted(config.manifest_dir.glob(f"{dataset_key}_*.json"))
    return candidates[-1] if candidates else None


def _normalize_lifecycle_payload(manifest: dict[str, Any], *, version: str) -> dict[str, Any]:
    payload = dict(manifest)
    dataset_key = str(payload.get("dataset_key") or payload.get("dataset") or "dataset")
    generated_at = str(payload.get("generated_at") or datetime.utcnow().isoformat(timespec="seconds") + "Z")
    payload["dataset_key"] = dataset_key
    payload["dataset_version"] = version
    payload["manifest_id"] = str(payload.get("manifest_id") or f"{dataset_key}:{version}")
    payload["generated_at"] = generated_at
    payload["valid_until"] = str(payload.get("valid_until") or _default_valid_until(generated_at))
    payload["superseded_by"] = payload.get("superseded_by")
    payload["status"] = _normalize_manifest_status(str(payload.get("status") or payload.get("quality_status") or "active"))
    return payload


def _default_valid_until(generated_at: str) -> str:
    try:
        parsed = datetime.fromisoformat(generated_at.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        parsed = datetime.utcnow()
    return (parsed + timedelta(days=7)).isoformat(timespec="seconds") + "Z"


def _normalize_manifest_status(status: str) -> str:
    normalized = str(status or "").strip().lower()
    if normalized in {"ok", "active"}:
        return "active"
    if normalized in {"stale", "partial", "blocked", "no_data"}:
        return normalized
    if normalized == "fail":
        return "blocked"
    return "partial"


def _load_previous_latest(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _mark_previous_superseded(previous: dict[str, Any] | None, *, superseded_by: str) -> None:
    if not previous:
        return
    previous_id = str(previous.get("manifest_id") or "")
    if previous_id == superseded_by:
        return
    previous_path = previous.get("manifest_path")
    if not previous_path:
        return
    path = Path(str(previous_path))
    if not path.exists():
        return
    previous["status"] = "stale"
    previous["superseded_by"] = superseded_by
    path.write_text(json.dumps(previous, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


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
