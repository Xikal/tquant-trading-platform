from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from app.core.config import get_settings
from app.models.schema_defs.bff import (
    MonitorWorkspaceBffResponse,
    PaperWorkspaceBffResponse,
    SettingsWorkspaceBffResponse,
    StrategyWorkspaceBffResponse,
)
from app.services.bff.remote_client import RemoteBffError, open_remote_bff_circuit, remote_bff_get

logger = logging.getLogger(__name__)


def load_remote_monitor_workspace(
    *,
    priority_limit: int,
    sector_limit: int,
    per_sector_limit: int,
    hedge_limit: int,
    view: str = "full",
    forward_headers: Mapping[str, str] | None = None,
) -> MonitorWorkspaceBffResponse | None:
    settings = get_settings()
    go_payload = _load_remote(
        settings.tquant_bff_gateway_url,
        "monitor",
        params={
            "priority_limit": priority_limit,
            "sector_limit": sector_limit,
            "per_sector_limit": per_sector_limit,
            "hedge_limit": hedge_limit,
            "view": view,
        },
        forward_headers=forward_headers,
    )
    go_response = _validate_remote_payload(MonitorWorkspaceBffResponse, go_payload, "monitor", settings.tquant_bff_gateway_url)
    if go_response is not None:
        return go_response
    payload = _load_remote(
        settings.tquant_market_service_url,
        "monitor",
        params={
            "priority_limit": priority_limit,
            "sector_limit": sector_limit,
            "per_sector_limit": per_sector_limit,
            "hedge_limit": hedge_limit,
            "view": view,
        },
        forward_headers=forward_headers,
    )
    return _validate_remote_payload(MonitorWorkspaceBffResponse, payload, "monitor", settings.tquant_market_service_url)


def load_remote_paper_workspace(
    *,
    order_limit: int,
    trade_limit: int,
    run_limit: int,
    forward_headers: Mapping[str, str] | None = None,
) -> PaperWorkspaceBffResponse | None:
    settings = get_settings()
    payload = _load_remote(
        settings.tquant_trade_service_url,
        "paper",
        params={"order_limit": order_limit, "trade_limit": trade_limit, "run_limit": run_limit},
        forward_headers=forward_headers,
    )
    return _validate_remote_payload(PaperWorkspaceBffResponse, payload, "paper", settings.tquant_trade_service_url)


def load_remote_strategy_workspace(
    *,
    run_limit: int,
    forward_headers: Mapping[str, str] | None = None,
) -> StrategyWorkspaceBffResponse | None:
    settings = get_settings()
    payload = _load_remote(
        settings.tquant_strategy_service_url,
        "strategy",
        params={"run_limit": run_limit},
        forward_headers=forward_headers,
    )
    return _validate_remote_payload(
        StrategyWorkspaceBffResponse,
        payload,
        "strategy",
        settings.tquant_strategy_service_url,
    )


def load_remote_settings_workspace(
    *,
    include_admin: bool,
    forward_headers: Mapping[str, str] | None = None,
) -> SettingsWorkspaceBffResponse | None:
    settings = get_settings()
    payload = _load_remote(
        settings.tquant_admin_service_url,
        "settings",
        params={"include_admin": str(include_admin).lower()},
        forward_headers=forward_headers,
    )
    return _validate_remote_payload(
        SettingsWorkspaceBffResponse,
        payload,
        "settings",
        settings.tquant_admin_service_url,
    )


def _load_remote(
    base_url: str,
    workspace: str,
    *,
    params: dict[str, Any],
    forward_headers: Mapping[str, str] | None,
) -> dict[str, Any] | None:
    if not base_url.strip():
        return None
    try:
        return remote_bff_get(
            base_url,
            _workspace_path(base_url, workspace),
            params=params,
            forward_headers=forward_headers,
        )
    except RemoteBffError:
        return None


def _workspace_path(base_url: str, workspace: str) -> str:
    return (
        f"/bff/v1/workspace/{workspace}"
        if base_url.rstrip("/").endswith("/api")
        else f"/api/bff/v1/workspace/{workspace}"
    )


def _validate_remote_payload(model: Any, payload: dict[str, Any] | None, workspace: str, base_url: str) -> Any | None:
    if not payload:
        return None
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        expected_fields = set(getattr(model, "model_fields", {}) or getattr(model, "__fields__", {}))
        actual_fields = set(payload)
        schema_version = str(payload.get("schema_version") or payload.get("api_version") or "unknown")
        logger.warning(
            "remote bff schema mismatch workspace=%s base_url=%s schema_version=%s missing_fields=%s extra_fields=%s errors=%s",
            workspace,
            base_url,
            schema_version,
            sorted(expected_fields - actual_fields),
            sorted(actual_fields - expected_fields),
            _validation_error_summary(exc),
        )
        open_remote_bff_circuit(base_url)
        return None


def _validation_error_summary(exc: ValidationError) -> list[dict[str, Any]]:
    """Keep diagnostics useful without logging remote payload values."""

    summary: list[dict[str, Any]] = []
    for item in exc.errors():
        summary.append(
            {
                "loc": item.get("loc"),
                "type": item.get("type"),
                "msg": item.get("msg"),
            }
        )
    return summary
