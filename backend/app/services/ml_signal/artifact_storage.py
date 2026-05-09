from __future__ import annotations

import hashlib
import posixpath
import shutil
from pathlib import Path


def safe_artifact_name(model_key: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in model_key)[:120]


def validated_artifact_path(artifact_uri: str, artifact_dir: Path) -> Path:
    base = artifact_dir.resolve()
    path = Path(artifact_uri).expanduser()
    resolved = path.resolve()
    if resolved.suffix != ".pkl":
        raise ValueError("invalid model artifact suffix")
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise ValueError("model artifact path escapes configured directory") from exc
    if not resolved.is_file():
        raise ValueError("model artifact file does not exist")
    return resolved


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_fsspec_uri(value: str) -> bool:
    return "://" in str(value or "") and not str(value or "").startswith("file://")


def join_fsspec_uri(base_uri: str, filename: str) -> str:
    cleaned = str(base_uri).rstrip("/")
    return f"{cleaned}/{filename}"


def fsspec_url_to_fs(uri: str):
    try:
        import fsspec
    except ImportError as exc:
        raise ValueError(
            "ml_signal_artifact_remote_dir uses a remote URI; install fsspec and the matching storage driver "
            "(for example s3fs/ossfs) to enable remote ML artifacts."
        ) from exc
    return fsspec.core.url_to_fs(uri)


def copy_local_to_fsspec(source: Path, target_uri: str) -> None:
    fs, target_path = fsspec_url_to_fs(target_uri)
    parent = posixpath.dirname(target_path)
    if parent:
        fs.makedirs(parent, exist_ok=True)
    with source.open("rb") as src, fs.open(target_path, "wb") as dst:
        shutil.copyfileobj(src, dst)


def copy_fsspec_to_local(source_uri: str, target: Path) -> None:
    fs, source_path = fsspec_url_to_fs(source_uri)
    if not fs.exists(source_path):
        raise ValueError("remote model artifact file does not exist")
    with fs.open(source_path, "rb") as src, target.open("wb") as dst:
        shutil.copyfileobj(src, dst)


def fsspec_sha256(uri: str) -> str:
    fs, path = fsspec_url_to_fs(uri)
    if not fs.exists(path):
        raise ValueError("remote model artifact file does not exist")
    digest = hashlib.sha256()
    with fs.open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def remove_fsspec_file(uri: str) -> None:
    fs, path = fsspec_url_to_fs(uri)
    if fs.exists(path):
        fs.rm(path)


def mask_storage_uri(value: str) -> str:
    if "://" not in value:
        return value
    scheme, rest = value.split("://", 1)
    if "@" not in rest:
        return value
    return f"{scheme}://***@{rest.rsplit('@', 1)[-1]}"
