from __future__ import annotations

import logging
import threading
import time

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.entities import SystemSetting

logger = logging.getLogger(__name__)

FRONTEND_NEXT_MONITOR_CUTOVER_SETTING_KEY = "frontend_next.monitor_cutover_enabled"
DEFAULT_LEVEL1_CUTOVER_PATHS = {"monitor"}
SUPPORTED_CUTOVER_PATHS = {
    "",
    "monitor",
    "monitor/market",
    "strategy-tracking",
    "analysis",
    "playbook",
    "backtest",
    "data",
    "settings",
}
_CACHE_TTL_SECONDS = 3.0
_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
_FALSE_VALUES = {"0", "false", "no", "off", "disabled"}
_cache_lock = threading.Lock()
_cache_deadline = 0.0
_cache_value: bool | None = None
_paths_cache_deadline = 0.0
_paths_cache_value: frozenset[str] | None = None


def frontend_next_monitor_cutover_enabled() -> bool:
    """Return the runtime /monitor cutover switch.

    A persisted system setting takes precedence over the container environment
    so operators can roll forward or back without rebuilding/restarting.  The
    environment setting remains a fallback for fresh deployments and DB outages.
    """

    global _cache_deadline, _cache_value
    now = time.monotonic()
    with _cache_lock:
        if _cache_value is not None and _cache_deadline > now:
            return _cache_value

    value = _read_runtime_value()
    with _cache_lock:
        _cache_value = value
        _cache_deadline = now + _CACHE_TTL_SECONDS
    return value


def frontend_next_cutover_paths() -> frozenset[str]:
    """Return legacy paths currently served by frontend-next.

    The existing monitor cutover switch remains the Level 1 compatibility
    fallback.  Operators can expand the cutover by setting
    FRONTEND_NEXT_CUTOVER_PATHS to a comma-separated allowlist.
    """

    global _paths_cache_deadline, _paths_cache_value
    now = time.monotonic()
    with _cache_lock:
        if _paths_cache_value is not None and _paths_cache_deadline > now:
            return _paths_cache_value

    value = _read_cutover_paths()
    with _cache_lock:
        _paths_cache_value = frozenset(value)
        _paths_cache_deadline = now + _CACHE_TTL_SECONDS
    return frozenset(value)


def clear_frontend_next_cutover_cache() -> None:
    global _cache_deadline, _cache_value, _paths_cache_deadline, _paths_cache_value
    with _cache_lock:
        _cache_value = None
        _cache_deadline = 0.0
        _paths_cache_value = None
        _paths_cache_deadline = 0.0


def _read_runtime_value() -> bool:
    fallback = bool(get_settings().frontend_next_monitor_cutover_enabled)
    try:
        with SessionLocal() as db:
            row = db.execute(
                select(SystemSetting).where(SystemSetting.key == FRONTEND_NEXT_MONITOR_CUTOVER_SETTING_KEY)
            ).scalar_one_or_none()
            if row is None:
                return fallback
            parsed = _parse_bool(row.value)
            return fallback if parsed is None else parsed
    except Exception:
        logger.warning("frontend-next cutover setting unavailable; falling back to environment")
        return fallback


def _parse_bool(value: str | None) -> bool | None:
    normalized = str(value or "").strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return None


def _read_cutover_paths() -> frozenset[str]:
    settings = get_settings()
    configured = _parse_paths(settings.frontend_next_cutover_paths)
    if configured:
        return configured
    if frontend_next_monitor_cutover_enabled():
        return frozenset(DEFAULT_LEVEL1_CUTOVER_PATHS)
    return frozenset()


def _parse_paths(value: str | None) -> frozenset[str]:
    requested = set()
    for item in str(value or "").replace(";", ",").split(","):
        raw = item.strip().lower()
        if not raw:
            continue
        normalized = "" if raw == "/" else raw.strip("/")
        if not normalized and raw != "/":
            continue
        requested.add(normalized)
    if "all" in requested:
        return frozenset(SUPPORTED_CUTOVER_PATHS)
    return frozenset(item for item in requested if item in SUPPORTED_CUTOVER_PATHS)
