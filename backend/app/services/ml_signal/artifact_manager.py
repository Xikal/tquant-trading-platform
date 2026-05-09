from __future__ import annotations

import pickle
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import BACKEND_DIR, get_settings
from app.models.schema_defs.phase4 import MLSignalArtifactStorageCheckResponse
from app.services.ml_signal.artifact_storage import (
    copy_fsspec_to_local,
    copy_local_to_fsspec,
    file_sha256,
    fsspec_sha256,
    is_fsspec_uri,
    join_fsspec_uri,
    mask_storage_uri,
    remove_fsspec_file,
    safe_artifact_name,
    validated_artifact_path,
)


class MLSignalArtifactManager:
    def artifact_dir(self) -> Path:
        configured = Path(get_settings().ml_signal_model_dir)
        base = configured if configured.is_absolute() else BACKEND_DIR / configured
        base.mkdir(parents=True, exist_ok=True)
        return base

    def save_artifact(self, *, model_key: str, payload: dict[str, Any]) -> tuple[str, str]:
        path = self.artifact_dir() / f"{safe_artifact_name(model_key)}.pkl"
        with path.open("wb") as file:
            pickle.dump(payload, file)
        return str(path), file_sha256(path)

    def backup_artifact(self, artifact_uri: str, expected_sha256: str) -> str:
        remote_dir_raw = (get_settings().ml_signal_artifact_remote_dir or "").strip()
        if not remote_dir_raw:
            return ""
        source = validated_artifact_path(artifact_uri, self.artifact_dir())
        if is_fsspec_uri(remote_dir_raw):
            target_uri = join_fsspec_uri(remote_dir_raw, source.name)
            copy_local_to_fsspec(source, target_uri)
            if fsspec_sha256(target_uri) != expected_sha256:
                remove_fsspec_file(target_uri)
                raise ValueError("remote artifact hash mismatch after backup")
            return target_uri
        remote_dir = Path(remote_dir_raw)
        if not remote_dir.is_absolute():
            remote_dir = BACKEND_DIR / remote_dir
        remote_dir.mkdir(parents=True, exist_ok=True)
        target = remote_dir / source.name
        if source.resolve() == target.resolve():
            return str(target)
        shutil.copy2(source, target)
        if file_sha256(target) != expected_sha256:
            target.unlink(missing_ok=True)
            raise ValueError("remote artifact hash mismatch after backup")
        return str(target)

    def load_artifact(
        self,
        artifact_uri: str,
        *,
        expected_sha256: str = "",
        remote_artifact_uri: str = "",
    ) -> dict[str, Any]:
        self.restore_artifact_if_missing(
            artifact_uri=artifact_uri,
            remote_artifact_uri=remote_artifact_uri,
            expected_sha256=expected_sha256,
        )
        path = validated_artifact_path(artifact_uri, self.artifact_dir())
        if not expected_sha256:
            raise ValueError("model artifact hash is missing")
        actual_sha256 = file_sha256(path)
        if actual_sha256 != expected_sha256:
            raise ValueError("model artifact hash mismatch")
        with path.open("rb") as file:
            payload = pickle.load(file)
        if not isinstance(payload, dict) or "estimator" not in payload:
            raise ValueError("invalid model artifact")
        return payload

    def restore_artifact_if_missing(
        self,
        *,
        artifact_uri: str,
        remote_artifact_uri: str,
        expected_sha256: str,
    ) -> None:
        if not remote_artifact_uri or not expected_sha256:
            return
        target = Path(artifact_uri).expanduser()
        base = self.artifact_dir().resolve()
        target_resolved = target.resolve()
        try:
            target_resolved.relative_to(base)
        except ValueError as exc:
            raise ValueError("model artifact restore path escapes configured directory") from exc
        if target.exists():
            return
        if is_fsspec_uri(remote_artifact_uri):
            if fsspec_sha256(remote_artifact_uri) != expected_sha256:
                raise ValueError("remote model artifact hash mismatch")
            target.parent.mkdir(parents=True, exist_ok=True)
            copy_fsspec_to_local(remote_artifact_uri, target)
            return
        remote = Path(remote_artifact_uri).expanduser()
        if not remote.is_file():
            return
        if file_sha256(remote) != expected_sha256:
            raise ValueError("remote model artifact hash mismatch")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(remote, target)

    def check_storage(self) -> MLSignalArtifactStorageCheckResponse:
        remote_dir_raw = (get_settings().ml_signal_artifact_remote_dir or "").strip()
        if not remote_dir_raw:
            return MLSignalArtifactStorageCheckResponse(
                ok=True,
                configured=False,
                backend="local",
                message="未配置远端模型存储，当前仅使用本地 artifact 目录。",
            )
        artifact_dir = self.artifact_dir()
        probe_name = f"storage_probe_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}.pkl"
        local_source = artifact_dir / probe_name
        local_restore = artifact_dir / f"restore_{probe_name}"
        with local_source.open("wb") as file:
            pickle.dump({"probe": "tquant_ml_artifact_storage", "created_at": datetime.utcnow().isoformat()}, file)
        expected_sha256 = file_sha256(local_source)
        try:
            if is_fsspec_uri(remote_dir_raw):
                backend = "fsspec"
                remote_uri = join_fsspec_uri(remote_dir_raw, probe_name)
                copy_local_to_fsspec(local_source, remote_uri)
                read_ok = fsspec_sha256(remote_uri) == expected_sha256
                if read_ok:
                    copy_fsspec_to_local(remote_uri, local_restore)
                restore_ok = local_restore.exists() and file_sha256(local_restore) == expected_sha256
                remove_fsspec_file(remote_uri)
                cleanup_ok = True
            else:
                backend = "filesystem"
                remote_dir = Path(remote_dir_raw)
                if not remote_dir.is_absolute():
                    remote_dir = BACKEND_DIR / remote_dir
                remote_dir.mkdir(parents=True, exist_ok=True)
                remote_path = remote_dir / probe_name
                shutil.copy2(local_source, remote_path)
                read_ok = file_sha256(remote_path) == expected_sha256
                if read_ok:
                    shutil.copy2(remote_path, local_restore)
                restore_ok = local_restore.exists() and file_sha256(local_restore) == expected_sha256
                remote_path.unlink(missing_ok=True)
                cleanup_ok = not remote_path.exists()
            ok = bool(read_ok and restore_ok and cleanup_ok)
            return MLSignalArtifactStorageCheckResponse(
                ok=ok,
                configured=True,
                backend=backend,
                remote_dir=mask_storage_uri(remote_dir_raw),
                write_ok=True,
                read_ok=read_ok,
                restore_ok=restore_ok,
                cleanup_ok=cleanup_ok,
                message="远端模型存储写入、读取、恢复、清理验收通过。" if ok else "远端模型存储验收未完全通过。",
            )
        except Exception as exc:
            return MLSignalArtifactStorageCheckResponse(
                ok=False,
                configured=True,
                backend="fsspec" if is_fsspec_uri(remote_dir_raw) else "filesystem",
                remote_dir=mask_storage_uri(remote_dir_raw),
                message=f"远端模型存储验收失败：{exc}",
            )
        finally:
            local_source.unlink(missing_ok=True)
            local_restore.unlink(missing_ok=True)
