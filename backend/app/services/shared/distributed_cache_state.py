from __future__ import annotations

import logging
import threading
import time

from redis import Redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_LOCK = threading.RLock()
_CLIENT: Redis | None = None
_HEALTHY_UNTIL = 0.0
_FAILED_UNTIL = 0.0
_HEALTHY_TTL_SECONDS = 300.0
_FAILED_TTL_SECONDS = 20.0


def get_distributed_cache_client() -> Redis | None:
    global _CLIENT, _HEALTHY_UNTIL, _FAILED_UNTIL

    now = time.monotonic()
    with _LOCK:
        if _CLIENT is not None and now < _HEALTHY_UNTIL:
            return _CLIENT
        if _CLIENT is None and now < _FAILED_UNTIL:
            return None
        url = get_settings().redis_url.strip()
        if not url:
            _CLIENT = None
            _FAILED_UNTIL = now + _FAILED_TTL_SECONDS
            return None
        try:
            client = Redis.from_url(url, socket_timeout=0.5, socket_connect_timeout=0.5)
            client.ping()
        except Exception:
            logger.warning("redis cache client initialization failed", exc_info=True)
            _CLIENT = None
            _FAILED_UNTIL = now + _FAILED_TTL_SECONDS
            return None
        _CLIENT = client
        _HEALTHY_UNTIL = now + _HEALTHY_TTL_SECONDS
        _FAILED_UNTIL = 0.0
        return _CLIENT


def clear_distributed_cache_client_state() -> None:
    global _CLIENT, _HEALTHY_UNTIL, _FAILED_UNTIL
    with _LOCK:
        _CLIENT = None
        _HEALTHY_UNTIL = 0.0
        _FAILED_UNTIL = 0.0
