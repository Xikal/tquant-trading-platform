from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from typing import Any

from app.core.config import get_settings
from app.models.schema_defs.phase4 import RuntimeTaskEventOut

logger = logging.getLogger(__name__)

_CHANNEL_PREFIX = "tquant:runtime-task"


def redis_runtime_task_events_enabled() -> bool:
    settings = get_settings()
    backend = (settings.runtime_event_pubsub_backend or "auto").strip().lower()
    if backend in {"off", "none", "database", "db"}:
        return False
    if not settings.redis_url:
        return False
    return _redis_module() is not None


def publish_runtime_task_event(event: RuntimeTaskEventOut) -> None:
    if not redis_runtime_task_events_enabled():
        return
    client = _redis_client()
    if client is None:
        return
    try:
        client.publish(_channel(event.task_id), json.dumps(event.model_dump(mode="json"), ensure_ascii=False))
    except Exception:
        logger.warning("failed to publish runtime task event to redis", exc_info=True)


def subscribe_runtime_task_events(
    task_id: int,
    *,
    timeout_seconds: int | None = None,
    heartbeat_seconds: float = 15.0,
) -> Iterator[dict[str, Any]]:
    """Yield Redis pub/sub runtime task events.

    The database event table remains the durable audit log. Redis is only the
    live fan-out layer, so caller code should fetch DB events before/around
    subscription to cover reconnects and late subscribers.
    """

    client = _redis_client()
    if client is None:
        return
    settings = get_settings()
    deadline = time.monotonic() + float(timeout_seconds or settings.runtime_event_stream_timeout_seconds)
    pubsub = client.pubsub(ignore_subscribe_messages=True)
    try:
        pubsub.subscribe(_channel(task_id))
        last_heartbeat = time.monotonic()
        while time.monotonic() < deadline:
            message = pubsub.get_message(timeout=1.0)
            now = time.monotonic()
            if message is None:
                if now - last_heartbeat >= heartbeat_seconds:
                    last_heartbeat = now
                    yield {"event_type": "heartbeat", "heartbeat": True}
                continue
            raw = message.get("data")
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="ignore")
            try:
                payload = json.loads(str(raw or "{}"))
            except json.JSONDecodeError:
                logger.warning("invalid redis runtime task event payload: %r", raw)
                continue
            if isinstance(payload, dict):
                yield payload
    finally:
        try:
            pubsub.unsubscribe(_channel(task_id))
            pubsub.close()
        except Exception:
            logger.debug("failed to close runtime task pubsub", exc_info=True)


def _channel(task_id: int) -> str:
    return f"{_CHANNEL_PREFIX}:{int(task_id)}"


def _redis_client():
    module = _redis_module()
    if module is None:
        return None
    try:
        return module.Redis.from_url(
            get_settings().redis_url,
            socket_connect_timeout=1.5,
            socket_timeout=2.0,
            decode_responses=False,
        )
    except Exception:
        logger.warning("failed to create redis client", exc_info=True)
        return None


def _redis_module():
    try:
        import redis  # type: ignore
    except Exception:
        return None
    return redis
