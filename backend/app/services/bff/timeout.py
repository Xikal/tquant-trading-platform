from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Callable, TypeVar

from app.models.schema_defs.bff import BffPartialError

logger = logging.getLogger(__name__)
T = TypeVar("T")

_BFF_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="bff-workspace")


def run_workspace_with_timeout(
    *,
    source: str,
    timeout_seconds: float,
    loader: Callable[[], T],
    fallback: Callable[[BffPartialError], T],
) -> T:
    if timeout_seconds <= 0:
        return loader()
    future = _BFF_EXECUTOR.submit(loader)
    try:
        return future.result(timeout=timeout_seconds)
    except TimeoutError:
        future.cancel()
        error = BffPartialError(
            source=source,
            detail="数据聚合超时，已返回降级结果",
            reason="timeout",
            timeout_ms=max(int(timeout_seconds * 1000), 0),
            fallback_source="python_local",
            message="workspace aggregation timeout",
        )
        logger.warning("bff workspace timed out source=%s timeout=%.2fs", source, timeout_seconds)
        return fallback(error)
