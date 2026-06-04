#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import io
import json
import os
import stat
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXCLUDE_PREFIXES = (
    ".git/",
    ".codex/",
    ".continue/",
    ".understand-anything/",
    ".runtime/",
    ".mysql-dist/",
    ".mysql-local/",
    "artifacts/",
    "backups/",
    "backend/.venv/",
    "backend/__pycache__/",
    "backend/.pytest_cache/",
    "frontend/node_modules/",
    "frontend/dist/",
)
EXCLUDE_EXACT = {
    ".git",
    ".codex",
    ".continue",
    ".understand-anything",
    ".runtime",
    ".mysql-dist",
    ".mysql-local",
    "artifacts",
    "backups",
    "backend/.env",
    "backend/data/runtime.env",
    "frontend/node_modules",
    "frontend/dist",
}
EXCLUDE_PATTERNS = (
    "backend/data/*.db",
    "backend/data/*.sqlite",
    "frontend/*.tsbuildinfo",
    "rust/*/target",
    "rust/*/target/*",
    "*.pyc",
    "*.pyo",
    "*.log",
    "._*",
    "*/._*",
    ".DS_Store",
    "*/.DS_Store",
)
PROTECTED_DELETE_PREFIXES = (
    ".env",
    ".runtime/",
    "backend/data/",
    "backups/",
    "artifacts/",
    ".mysql-dist/",
    ".mysql-local/",
)
PROTECTED_DELETE_PATTERNS = (
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "*.bak",
    "*.backup",
    "*.dump",
    "*.sql",
    "*.tgz",
    "*.tar.gz",
)
CRITICAL_EXACT = {
    "Dockerfile",
    "docker-compose.mysql.yml",
    "docker-compose.sqlite.yml",
    "requirements.txt",
    "backend/requirements.txt",
    "backend/requirements-analytics.txt",
    "backend/requirements-dev.txt",
    "backend/requirements-ml-extra.txt",
    "backend/requirements-rl-extra.txt",
    "backend/alembic.ini",
    "docs/contracts/openapi.json",
    "docs/contracts/openapi.hash",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/src/generated/api-types.ts",
    "scripts/deploy_cloud_server.sh",
    "scripts/deploy_delta_package.py",
    "scripts/quick_cloud_deploy.sh",
    "scripts/one_click_cloud_deploy.sh",
    "scripts/run_platform_component.sh",
    "backend/scripts/analytics_worker.py",
    "scripts/backtest_worker.py",
}
CRITICAL_PREFIXES = (
    "backend/alembic/",
    "frontend/src/generated/",
    "docs/contracts/openapi.",
    "backend/app/workers/",
)
CRITICAL_PATTERNS = (
    "docker-compose.*.yml",
    "backend/requirements*.txt",
    "frontend/package-lock.json",
)
DEFAULT_MAX_CHANGE_RATIO = 0.35


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalized_rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def invalid_relpath(value: str) -> bool:
    return value.startswith("/") or value == "" or ".." in Path(value).parts


def should_exclude(rel: str) -> bool:
    if rel in EXCLUDE_EXACT:
        return True
    if any(rel.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
        return True
    return any(fnmatch.fnmatch(rel, pattern) for pattern in EXCLUDE_PATTERNS)


def protected_delete(rel: str) -> bool:
    if invalid_relpath(rel):
        return True
    if rel == ".env" or rel.startswith(PROTECTED_DELETE_PREFIXES):
        return True
    return any(fnmatch.fnmatch(rel, pattern) for pattern in PROTECTED_DELETE_PATTERNS)


def critical_path(rel: str) -> bool:
    if rel in CRITICAL_EXACT:
        return True
    if any(rel.startswith(prefix) for prefix in CRITICAL_PREFIXES):
        return True
    return any(fnmatch.fnmatch(rel, pattern) for pattern in CRITICAL_PATTERNS)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: Path) -> dict[str, Any]:
    files: dict[str, dict[str, Any]] = {}
    root = root.resolve()
    for path in sorted(root.rglob("*")):
        rel = normalized_rel(path, root)
        if should_exclude(rel):
            continue
        if path.is_dir():
            continue
        if not path.is_file():
            continue
        st = path.stat()
        files[rel] = {
            "sha256": file_sha256(path),
            "size": int(st.st_size),
            "mode": oct(stat.S_IMODE(st.st_mode)),
        }
    return {
        "version": 1,
        "generated_at": utc_now(),
        "file_count": len(files),
        "total_size": sum(int(item["size"]) for item in files.values()),
        "files": files,
    }


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def compare_manifests(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    *,
    max_change_ratio: float,
) -> tuple[dict[str, Any], str]:
    if not previous:
        return _summary(current, [], [], [], "missing_remote_manifest", 0.0), "missing_remote_manifest"

    current_files = current.get("files") or {}
    previous_files = previous.get("files") or {}
    changed: list[str] = []
    deleted: list[str] = []
    unsafe_deletes: list[str] = []
    critical: list[str] = []

    for rel, info in current_files.items():
        old = previous_files.get(rel)
        if old is None or old.get("sha256") != info.get("sha256") or old.get("mode") != info.get("mode"):
            changed.append(rel)

    for rel in previous_files:
        if rel not in current_files:
            deleted.append(rel)
            if protected_delete(rel):
                unsafe_deletes.append(rel)

    for rel in [*changed, *deleted]:
        if critical_path(rel):
            critical.append(rel)

    denominator = max(len(current_files), 1)
    change_ratio = (len(changed) + len(deleted)) / denominator
    fallback_reason = ""
    if unsafe_deletes:
        fallback_reason = "unsafe_delete_paths"
    elif critical:
        fallback_reason = "critical_paths_changed"
    elif change_ratio > max_change_ratio:
        fallback_reason = "change_ratio_too_high"

    return _summary(current, changed, deleted, critical, fallback_reason, change_ratio, unsafe_deletes), fallback_reason


def _summary(
    current: dict[str, Any],
    changed: list[str],
    deleted: list[str],
    critical: list[str],
    fallback_reason: str,
    change_ratio: float,
    unsafe_deletes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "sync_mode": "delta-package",
        "generated_at": utc_now(),
        "changed_count": len(changed),
        "deleted_count": len(deleted),
        "changed_files": changed,
        "deleted_files": deleted,
        "critical_files": critical,
        "unsafe_delete_files": unsafe_deletes or [],
        "fallback_reason": fallback_reason,
        "change_ratio": round(change_ratio, 6),
        "delta_bytes": 0,
        "full_bytes": int(current.get("total_size") or 0),
        "file_count": int(current.get("file_count") or 0),
    }


def add_json_to_tar(tar: tarfile.TarFile, arcname: str, payload: dict[str, Any]) -> None:
    data = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    info = tarfile.TarInfo(arcname)
    info.size = len(data)
    info.mtime = int(datetime.now(timezone.utc).timestamp())
    info.mode = 0o644
    tar.addfile(info, io.BytesIO(data))


def create_delta_archive(root: Path, output: Path, current: dict[str, Any], previous: dict[str, Any], summary: dict[str, Any]) -> int:
    changed = list(summary["changed_files"])
    deleted = list(summary["deleted_files"])
    delete_manifest = {
        "version": 1,
        "generated_at": utc_now(),
        "files": [
            {
                "path": rel,
                "sha256": (previous.get("files") or {}).get(rel, {}).get("sha256", ""),
                "mode": (previous.get("files") or {}).get(rel, {}).get("mode", ""),
            }
            for rel in deleted
        ],
    }
    delta_manifest = {
        "version": 1,
        "generated_at": utc_now(),
        "changed_files": changed,
        "deleted_files": deleted,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, "w:gz") as tar:
        for rel in changed:
            tar.add(root / rel, arcname=f"./{rel}", recursive=False)
        add_json_to_tar(tar, "./.deploy-delta/deploy-manifest.json", current)
        add_json_to_tar(tar, "./.deploy-delta/deploy-delete-manifest.json", delete_manifest)
        add_json_to_tar(tar, "./.deploy-delta/deploy-delta-manifest.json", delta_manifest)
    return output.stat().st_size


def build_delta(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    current = build_manifest(root)
    dump_json(Path(args.manifest_output), current)

    previous_path = Path(args.previous)
    previous = load_json(previous_path) if previous_path.is_file() else None
    summary, fallback_reason = compare_manifests(
        current,
        previous,
        max_change_ratio=float(args.max_change_ratio),
    )
    if previous and not fallback_reason:
        summary["delta_bytes"] = create_delta_archive(root, Path(args.output), current, previous, summary)
    dump_json(Path(args.summary_output), summary)
    return 0


def apply_deletes(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    previous = load_json(Path(args.previous_manifest))
    delete_manifest = load_json(Path(args.delete_manifest))
    previous_files = previous.get("files") or {}
    deleted = 0
    for item in delete_manifest.get("files") or []:
        rel = str(item.get("path") or "")
        if protected_delete(rel):
            raise ValueError(f"unsafe delete path: {rel}")
        previous_info = previous_files.get(rel)
        if previous_info is None:
            raise ValueError(f"delete path is not manifest-bounded: {rel}")
        if str(item.get("sha256") or "") != str(previous_info.get("sha256") or ""):
            raise ValueError(f"delete sha256 mismatch: {rel}")
        target = (root / rel).resolve()
        if root not in target.parents and target != root:
            raise ValueError(f"delete path escapes root: {rel}")
        if target.is_file() or target.is_symlink():
            target.unlink()
            deleted += 1
    summary = {"deleted_count": deleted}
    if args.summary_output:
        dump_json(Path(args.summary_output), summary)
    return 0


def summary_env(args: argparse.Namespace) -> int:
    summary = load_json(Path(args.summary))
    values = {
        "DEPLOY_DELTA_CHANGED_COUNT": int(summary.get("changed_count") or 0),
        "DEPLOY_DELTA_DELETED_COUNT": int(summary.get("deleted_count") or 0),
        "DEPLOY_DELTA_BYTES": int(summary.get("delta_bytes") or 0),
        "DEPLOY_DELTA_FULL_BYTES": int(summary.get("full_bytes") or 0),
        "DEPLOY_DELTA_FALLBACK_REASON": str(summary.get("fallback_reason") or ""),
    }
    for key, value in values.items():
        print(f"{key}={json.dumps(str(value))}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and apply deploy delta packages.")
    sub = parser.add_subparsers(dest="command", required=True)

    manifest_parser = sub.add_parser("manifest")
    manifest_parser.add_argument("--root", required=True)
    manifest_parser.add_argument("--output", required=True)
    manifest_parser.add_argument("--quiet", action="store_true")

    build_parser = sub.add_parser("build")
    build_parser.add_argument("--root", required=True)
    build_parser.add_argument("--previous", required=True)
    build_parser.add_argument("--output", required=True)
    build_parser.add_argument("--manifest-output", required=True)
    build_parser.add_argument("--summary-output", required=True)
    build_parser.add_argument("--max-change-ratio", type=float, default=DEFAULT_MAX_CHANGE_RATIO)

    apply_parser = sub.add_parser("apply-deletes")
    apply_parser.add_argument("--root", required=True)
    apply_parser.add_argument("--previous-manifest", required=True)
    apply_parser.add_argument("--delete-manifest", required=True)
    apply_parser.add_argument("--summary-output", default="")

    summary_parser = sub.add_parser("summary-env")
    summary_parser.add_argument("--summary", required=True)

    args = parser.parse_args()
    if args.command == "manifest":
        manifest = build_manifest(Path(args.root))
        dump_json(Path(args.output), manifest)
        if not args.quiet:
            print(json.dumps({"file_count": manifest["file_count"], "total_size": manifest["total_size"]}))
        return 0
    if args.command == "build":
        return build_delta(args)
    if args.command == "apply-deletes":
        return apply_deletes(args)
    if args.command == "summary-env":
        return summary_env(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
