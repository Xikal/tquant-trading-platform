from __future__ import annotations

import json
import logging
from typing import Any

from redis.exceptions import RedisError, TimeoutError as RedisTimeoutError

from app.core.config import get_settings
from app.services.performance.read_model_metrics import record_cache_operation_error
from app.services.shared.distributed_cache_state import (
    clear_distributed_cache_client_state,
    get_distributed_cache_client,
    mark_distributed_cache_unhealthy,
)

logger = logging.getLogger(__name__)


def get_text_cache(key: str, *, fail_open: bool | None = None) -> str | None:
    client = get_distributed_cache_client()
    if client is None:
        return None
    try:
        value = client.get(key)
    except _CACHE_EXCEPTIONS as exc:
        _handle_cache_error("get", key=key, exc=exc, fail_open=fail_open)
        return None
    if value is None:
        return None
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def set_text_cache(key: str, value: str, ttl_seconds: int | float, *, fail_open: bool | None = None) -> bool:
    client = get_distributed_cache_client()
    if client is None:
        return False
    try:
        client.setex(key, max(int(ttl_seconds), 1), value)
        return True
    except _CACHE_EXCEPTIONS as exc:
        _handle_cache_error("set", key=key, exc=exc, fail_open=fail_open)
        return False


def get_json_cache(key: str) -> Any | None:
    raw = get_text_cache(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("redis cache json decode failed key=%s", key, exc_info=True)
    return None


def get_many_json_cache(keys: list[str], *, fail_open: bool | None = None) -> dict[str, Any]:
    if not keys:
        return {}
    client = get_distributed_cache_client()
    if client is None:
        return {}
    try:
        raw_values = client.mget(keys)
    except _CACHE_EXCEPTIONS as exc:
        _handle_cache_error("mget", key=str(len(keys)), exc=exc, fail_open=fail_open)
        return {}
    result: dict[str, Any] = {}
    for key, raw in zip(keys, raw_values):
        if raw is None:
            continue
        text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
        try:
            result[key] = json.loads(text)
        except (TypeError, ValueError):
            logger.warning("redis cache json decode failed key=%s", key, exc_info=True)
    return result


def set_json_cache(key: str, value: Any, ttl_seconds: int | float) -> bool:
    try:
        payload = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        logger.warning("redis cache json encode failed key=%s", key, exc_info=True)
        return False
    return set_text_cache(key, payload, ttl_seconds)


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
    except _CACHE_EXCEPTIONS as exc:
        _handle_cache_error("mset", key=str(len(values)), exc=exc, fail_open=True)
        return 0


def clear_distributed_cache_client() -> None:
    clear_distributed_cache_client_state()


_CACHE_EXCEPTIONS = (RedisError, RedisTimeoutError, OSError, TimeoutError)


def _cache_error_reason(exc: BaseException) -> str:
    text = str(exc).lower()
    if isinstance(exc, (TimeoutError, RedisTimeoutError)) or "timeout" in text:
        return "timeout"
    if "connection" in text or "disconnect" in text or "reset" in text:
        return "connection"
    if isinstance(exc, RedisError):
        return "redis_error"
    return "other"


def _record_cache_error(operation: str, reason: str) -> None:
    record_cache_operation_error(cache_name="distributed", operation=operation, reason=reason)


def _cache_fail_open_enabled(fail_open: bool | None) -> bool:
    if fail_open is not None:
        return bool(fail_open)
    return bool(get_settings().distributed_cache_fail_open_enabled)


def _handle_cache_error(operation: str, *, key: str, exc: BaseException, fail_open: bool | None) -> None:
    mark_distributed_cache_unhealthy()
    reason = _cache_error_reason(exc)
    _record_cache_error(operation, reason)
    logger.warning("redis cache %s failed key=%s reason=%s", operation, key, reason, exc_info=True)
    if not _cache_fail_open_enabled(fail_open):
        raise exc
