from __future__ import annotations

import json
from typing import Any

from app.services.performance.read_model_metrics import (
    record_read_model_cache_hit,
    record_read_model_cache_miss,
    record_read_model_cache_write,
)
from app.services.shared.distributed_cache import get_text_cache, set_text_cache

READ_MODEL_VERSION = "v1"
_MODEL_NAME = "priority_board_stable"


def priority_board_read_model_key(
    *,
    trade_date: str,
    strategy_variant: str,
    cache_key: str,
    user_filter_hash: str = "global",
) -> str:
    return ":".join(
        [
            "priority_board_read_model",
            READ_MODEL_VERSION,
            str(trade_date or "unknown"),
            str(strategy_variant or "default"),
            str(cache_key or "none"),
            str(user_filter_hash or "global"),
        ]
    )


def load_priority_board_read_model(key: str) -> dict[str, Any] | None:
    raw = get_text_cache(key)
    if not raw:
        record_read_model_cache_miss(_MODEL_NAME)
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        record_read_model_cache_miss(_MODEL_NAME)
        return None
    if not isinstance(payload, dict):
        record_read_model_cache_miss(_MODEL_NAME)
        return None
    record_read_model_cache_hit(_MODEL_NAME)
    return payload


def store_priority_board_read_model(key: str, payload: dict[str, Any], *, ttl_seconds: int) -> bool:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    stored = set_text_cache(key, raw, ttl_seconds=ttl_seconds)
    if stored:
        record_read_model_cache_write(_MODEL_NAME)
    return stored
