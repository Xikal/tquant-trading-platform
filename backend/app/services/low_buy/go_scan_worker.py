from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from app.core.config import get_settings
from app.services.bff.remote_client import RemoteBffError, remote_bff_get


logger = logging.getLogger(__name__)


def run_go_scan_worker(
    *,
    strategies: Iterable[str],
    scan_limit: int,
    limit: int,
    reason: str,
) -> dict[str, Any]:
    """Run the Go scan-worker production scan path when configured.

    Python remains the business-rule reference and fallback, but production
    schedulers now call Go first so hit/fallback state is observable.
    """

    settings = get_settings()
    base_url = settings.tquant_go_scan_worker_url.strip()
    if not base_url or not settings.tquant_go_scan_enabled:
        return {
            "ok": False,
            "enabled": False,
            "fallback_reason": "go_scan_worker_disabled",
            "triggered": 0,
            "failed": 0,
        }

    cleaned = sorted({item.strip() for item in strategies if item and item.strip()})
    if not cleaned:
        return {
            "ok": False,
            "enabled": True,
            "fallback_reason": "no_strategies",
            "triggered": 0,
            "failed": 0,
        }
    try:
        payload = remote_bff_get(
            base_url,
            "/api/scan-worker/v1/run",
            params={
                "strategies": ",".join(cleaned),
                "scan_limit": max(int(scan_limit or 0), 1),
                "limit": max(int(limit or 0), 1),
                "reason": reason,
            },
        )
    except RemoteBffError as exc:
        logger.warning("go scan-worker production run failed error=%s", exc)
        return {
            "ok": False,
            "enabled": True,
            "fallback_reason": str(exc) or "go_scan_worker_unavailable",
            "triggered": 0,
            "failed": len(cleaned),
        }
    if not bool(payload.get("ok", False)):
        return {
            **payload,
            "ok": False,
            "enabled": True,
            "fallback_reason": payload.get("fallback_reason") or payload.get("detail") or "go_scan_worker_rejected",
        }
    return {**payload, "enabled": True, "fallback_reason": ""}
