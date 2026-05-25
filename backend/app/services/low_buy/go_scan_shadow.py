from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from app.core.config import get_settings
from app.services.bff.remote_client import remote_bff_get


logger = logging.getLogger(__name__)


def trigger_go_scan_shadow(
    *,
    strategies: Iterable[str],
    scan_limit: int,
    reason: str,
) -> dict[str, Any]:
    """Trigger optional Go scan-worker shadow runs after Python materialization.

    The Python low-buy pipeline remains the source of truth. This seam only lets
    operators validate Go scan-worker reachability and contract behavior without
    allowing Go to write production snapshots.
    """

    settings = get_settings()
    base_url = settings.tquant_go_scan_worker_url.strip()
    if not base_url or not settings.tquant_go_scan_shadow_enabled:
        return {"enabled": False, "triggered": 0, "failed": 0}

    triggered = 0
    failed = 0
    for strategy in sorted({item.strip() for item in strategies if item and item.strip()}):
        try:
            remote_bff_get(
                base_url,
                "/api/scan-worker/v1/shadow/run",
                params={
                    "strategy": strategy,
                    "limit": max(int(scan_limit or 0), 1),
                    "reason": reason,
                },
            )
            triggered += 1
        except Exception as exc:  # pragma: no cover - logging path only.
            failed += 1
            logger.warning("go scan-worker shadow trigger failed strategy=%s error=%s", strategy, exc)
    if triggered or failed:
        logger.info("go scan-worker shadow trigger completed triggered=%s failed=%s", triggered, failed)
    return {"enabled": True, "triggered": triggered, "failed": failed}
