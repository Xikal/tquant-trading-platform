from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, TypeVar

from fastapi import BackgroundTasks
from pydantic import ValidationError

from app.core.config import get_settings
from app.models.schema_defs.bff import BffManifestResponse
from app.services.bff.remote_client import RemoteBffError, remote_bff_get

logger = logging.getLogger(__name__)
T = TypeVar("T")


def schedule_go_bff_shadow_check(
    background_tasks: BackgroundTasks,
    *,
    workspace: str,
    response_model: type[T],
    local_payload: Any,
    request_headers: Mapping[str, str] | None = None,
    params: dict[str, Any] | None = None,
) -> bool:
    settings = get_settings()
    gateway = settings.tquant_bff_gateway_url.strip()
    if not gateway or not settings.tquant_bff_shadow_enabled:
        return False
    background_tasks.add_task(
        _run_go_bff_shadow_check,
        gateway,
        workspace,
        response_model,
        _dump_payload(local_payload),
        params or {},
        dict(request_headers or {}),
    )
    return True


def _run_go_bff_shadow_check(
    gateway: str,
    workspace: str,
    response_model: type[Any],
    local_payload: dict[str, Any],
    params: dict[str, Any],
    request_headers: dict[str, str],
) -> None:
    try:
        remote_payload = remote_bff_get(
            gateway,
            _shadow_path(gateway, workspace),
            params=params,
            forward_headers=request_headers,
        )
    except RemoteBffError as exc:
        logger.warning(
            "go bff shadow request failed workspace=%s gateway=%s error=%s",
            workspace,
            gateway,
            exc,
        )
        return

    try:
        remote_model = response_model.model_validate(remote_payload)
    except ValidationError as exc:
        logger.warning(
            "go bff shadow schema mismatch workspace=%s gateway=%s errors=%s",
            workspace,
            gateway,
            _validation_error_summary(exc),
        )
        return

    local_keys = set(local_payload)
    remote_keys = set(remote_payload)
    schema_version = str(remote_payload.get("schema_version") or remote_payload.get("api_version") or "unknown")

    if local_keys != remote_keys:
        logger.warning(
            "go bff shadow field diff workspace=%s gateway=%s schema_version=%s missing_fields=%s extra_fields=%s",
            workspace,
            gateway,
            schema_version,
            sorted(local_keys - remote_keys),
            sorted(remote_keys - local_keys),
        )
        return

    if isinstance(remote_model, BffManifestResponse):
        _log_manifest_parity(gateway, local_payload, remote_payload)
        return

    if local_payload.get("schema_version") != remote_payload.get("schema_version"):
        logger.warning(
            "go bff shadow schema version mismatch workspace=%s gateway=%s local=%s remote=%s",
            workspace,
            gateway,
            local_payload.get("schema_version"),
            remote_payload.get("schema_version"),
        )


def _log_manifest_parity(gateway: str, local_payload: dict[str, Any], remote_payload: dict[str, Any]) -> None:
    local_workspaces = set((local_payload.get("workspaces") or {}).keys())
    remote_workspaces = set((remote_payload.get("workspaces") or {}).keys())
    if local_workspaces != remote_workspaces:
        logger.warning(
            "go bff manifest shadow mismatch gateway=%s missing_workspaces=%s extra_workspaces=%s",
            gateway,
            sorted(local_workspaces - remote_workspaces),
            sorted(remote_workspaces - local_workspaces),
        )
        return
    for key in sorted(local_workspaces):
        local_item = (local_payload.get("workspaces") or {}).get(key) or {}
        remote_item = (remote_payload.get("workspaces") or {}).get(key) or {}
        if local_item.get("schema_version") != remote_item.get("schema_version"):
            logger.warning(
                "go bff manifest workspace schema mismatch gateway=%s workspace=%s local=%s remote=%s",
                gateway,
                key,
                local_item.get("schema_version"),
                remote_item.get("schema_version"),
            )


def _workspace_path(base_url: str, workspace: str) -> str:
    return (
        f"/bff/v1/workspace/{workspace}"
        if base_url.rstrip("/").endswith("/api")
        else f"/api/bff/v1/workspace/{workspace}"
    )


def _shadow_path(base_url: str, workspace: str) -> str:
    if workspace == "manifest":
        return "/bff/v1/manifest" if base_url.rstrip("/").endswith("/api") else "/api/bff/v1/manifest"
    return _workspace_path(base_url, workspace)


def _dump_payload(payload: Any) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return dict(payload.model_dump())
    if isinstance(payload, Mapping):
        return dict(payload)
    return dict(getattr(payload, "__dict__", {}))


def _validation_error_summary(exc: ValidationError) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for item in exc.errors():
        summary.append({"loc": item.get("loc"), "type": item.get("type"), "msg": item.get("msg")})
    return summary
