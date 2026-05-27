from __future__ import annotations

import json
import logging
from typing import Any

from redis.exceptions import RedisError

from app.services.shared.distributed_cache_state import (
    clear_distributed_cache_client_state,
    get_distributed_cache_client,
    mark_distributed_cache_unhealthy,
)

logger = logging.getLogger(__name__)


def get_text_cache(key: str) -> str | None:
    client = get_distributed_cache_client()
    if client is None:
        return None
    try:
        value = client.get(key)
    except RedisError:
        mark_distributed_cache_unhealthy()
        logger.warning("redis cache read failed key=%s", key, exc_info=True)
        return None
    if value is None:
        return None
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def set_text_cache(key: str, value: str, ttl_seconds: int | float) -> None:
    client = get_distributed_cache_client()
    if client is None:
        return
    try:
        client.setex(key, max(int(ttl_seconds), 1), value)
    except RedisError:
        mark_distributed_cache_unhealthy()
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


def set_many_json_cache(values: dict[str, Any], ttl_seconds: int | float) -> int:
    if not values:
        return 0
    client = get_distributed_cache_client()
    if client is None:
        return 0
    ttl = max(int(ttl_seconds), 1)
    try:
        with client.pipeline(transaction=False) as pipe:
            written = 0
            for key, value in values.items():
                try:
                    payload = json.dumps(value, ensure_ascii=False, default=str)
                except (TypeError, ValueError):
                    logger.warning("redis cache json encode failed key=%s", key, exc_info=True)
                    continue
                pipe.setex(key, ttl, payload)
                written += 1
            if written:
                pipe.execute()
            return written
    except RedisError:
        mark_distributed_cache_unhealthy()
        logger.warning("redis cache batch write failed keys=%s", len(values), exc_info=True)
        return 0


def clear_distributed_cache_client() -> None:
    clear_distributed_cache_client_state()
