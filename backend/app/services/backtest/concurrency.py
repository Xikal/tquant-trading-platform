from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator

from app.services.low_buy.strategy_parameter_defaults import BACKTEST_EXECUTION_DEFAULTS
from app.services.quant.runtime_parameters import get_backtest_execution

_LOCK = threading.Lock()
_SEMAPHORE: threading.BoundedSemaphore | None = None
_SEMAPHORE_SIZE = 0
_ACTIVE_SLOTS = 0


def max_concurrent_backtests() -> int:
    try:
        params = get_backtest_execution()
        raw = params.get("max_concurrent_backtests") or BACKTEST_EXECUTION_DEFAULTS["max_concurrent_backtests"]
        value = int(float(raw))
    except Exception:
        value = int(BACKTEST_EXECUTION_DEFAULTS["max_concurrent_backtests"])
    return max(1, min(value, 8))


@contextmanager
def backtest_execution_slot() -> Iterator[bool]:
    """Process-local CPU guard for backtest execution.

    Database queue checks limit cross-process concurrency; this semaphore adds a
    cheap process-level guard so a single worker process cannot run unbounded
    CPU-heavy jobs if worker topology changes.
    """

    acquired = _acquire_slot()
    try:
        yield acquired
    finally:
        if acquired:
            _release_slot()


def _acquire_slot() -> bool:
    global _ACTIVE_SLOTS, _SEMAPHORE, _SEMAPHORE_SIZE
    desired_size = max_concurrent_backtests()
    with _LOCK:
        if _SEMAPHORE is None or (_SEMAPHORE_SIZE != desired_size and _ACTIVE_SLOTS == 0):
            _SEMAPHORE = threading.BoundedSemaphore(desired_size)
            _SEMAPHORE_SIZE = desired_size
        semaphore = _SEMAPHORE
    if semaphore is None or not semaphore.acquire(blocking=False):
        return False
    with _LOCK:
        _ACTIVE_SLOTS += 1
    return True


def _release_slot() -> None:
    global _ACTIVE_SLOTS
    with _LOCK:
        semaphore = _SEMAPHORE
        _ACTIVE_SLOTS = max(_ACTIVE_SLOTS - 1, 0)
    if semaphore is not None:
        semaphore.release()
