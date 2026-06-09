from __future__ import annotations

import hashlib
import json
import logging
import threading
from collections.abc import Callable, Mapping
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.services.performance.read_model_metrics import (
    record_read_model_cache_hit,
    record_read_model_cache_miss,
    record_read_model_cache_stale,
    record_read_model_cache_write,
)
from app.services.shared.distributed_cache import get_json_cache, set_json_cache

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)
READ_MODEL_CACHE_VERSION = "bff-workspace-v1"
_METRICS_LOCK = threading.Lock()
_METRICS = {
    "reads": 0,
    "hits": 0,
    "writes": 0,
    "skips": 0,
    "schema_misses": 0,
}


def load_cached_workspace(
    *,
    workspace: str,
    model: type[T],
    user_id: int | str,
    params: Mapping[str, object],
    loader: Callable[[], T],
) -> T:
    settings = get_settings()
    ttl = _workspace_ttl(settings, workspace)
    if not settings.bff_workspace_cache_enabled or ttl <= 0:
        _increment("skips")
        return loader()

    key = _cache_key(workspace=workspace, user_id=user_id, params=params)
    _increment("reads")
    cached = get_json_cache(key)
    if isinstance(cached, dict):
        try:
            _increment("hits")
            record_read_model_cache_hit(f"bff_{workspace}")
            return model.model_validate(cached)
        except ValidationError:
            _increment("schema_misses")
            record_read_model_cache_stale(f"bff_{workspace}")
            logger.warning("bff workspace cache schema mismatch workspace=%s", workspace, exc_info=True)

    record_read_model_cache_miss(f"bff_{workspace}")
    result = loader()
    if _cacheable(result):
        _increment("writes")
        record_read_model_cache_write(f"bff_{workspace}")
        set_json_cache(key, result.model_dump(mode="json"), ttl)
    return result


def bff_workspace_cache_metrics_snapshot() -> dict[str, int]:
    with _METRICS_LOCK:
        return dict(_METRICS)


def _cacheable(result: BaseModel) -> bool:
    partial_errors = getattr(result, "partial_errors", None)
    return not partial_errors


def _workspace_ttl(settings, workspace: str) -> int:
    if workspace == "monitor":
        return int(settings.bff_monitor_cache_ttl_seconds or 0)
    if workspace == "strategy":
        return int(settings.bff_strategy_cache_ttl_seconds or 0)
    if workspace == "settings":
        return int(settings.bff_settings_cache_ttl_seconds or 0)
    return 0


def _cache_key(*, workspace: str, user_id: int | str, params: Mapping[str, object]) -> str:
    normalized = json.dumps(
        {"user_id": str(user_id), "params": dict(sorted((str(k), str(v)) for k, v in params.items()))},
        ensure_ascii=False,
        sort_keys=True,
    )
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"tq:bff:{READ_MODEL_CACHE_VERSION}:{workspace}:{digest}"


def _increment(key: str) -> None:
    with _METRICS_LOCK:
        _METRICS[key] = int(_METRICS.get(key, 0)) + 1
