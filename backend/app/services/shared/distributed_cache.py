from __future__ import annotations

import logging
import json
from functools import lru_cache
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _redis_client() -> Redis | None:
    url = get_settings().redis_url.strip()
    if not url:
        return None
    try:
        return Redis.from_url(url, socket_timeout=0.5, socket_connect_timeout=0.5)
    except Exception:
        logger.warning("redis cache client initialization failed", exc_info=True)
        return None


def get_text_cache(key: str) -> str | None:
    client = _redis_client()
    if client is None:
        return None
    try:
        value = client.get(key)
    except RedisError:
        logger.warning("redis cache read failed key=%s", key, exc_info=True)
        return None
    if value is None:
        return None
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def set_text_cache(key: str, value: str, ttl_seconds: int | float) -> None:
    client = _redis_client()
    if client is None:
        return
    try:
        client.setex(key, max(int(ttl_seconds), 1), value)
    except RedisError:
        logger.warning("redis cache write failed key=%s", key, exc_info=True)


def get_json_cache(key: str) -> Any | None:
    raw = get_text_cache(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("redis cache json decode failed key=%s", key, exc_info=True)
        return None


def set_json_cache(key: str, value: Any, ttl_seconds: int | float) -> None:
    try:
        payload = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        logger.warning("redis cache json encode failed key=%s", key, exc_info=True)
        return
    set_text_cache(key, payload, ttl_seconds)


def clear_distributed_cache_client() -> None:
    _redis_client.cache_clear()
