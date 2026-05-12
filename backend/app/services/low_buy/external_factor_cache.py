from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import TypeVar


T = TypeVar("T")

_KEY_LOCKS: dict[str, threading.Lock] = {}
_KEY_LOCKS_LOCK = threading.Lock()


def read_ttl_cache(cache: dict, lock: threading.RLock, key: str):
    with lock:
        cached = cache.get(key)
        if not cached:
            return None
        expires_at, value = cached
        if expires_at <= time.monotonic():
            cache.pop(key, None)
            return None
        return value


def write_ttl_cache(cache: dict, lock: threading.RLock, key: str, value, ttl_seconds: int) -> None:
    with lock:
        cache[key] = (time.monotonic() + ttl_seconds, value)


def get_or_load_ttl_cache(
    cache: dict,
    lock: threading.RLock,
    *,
    namespace: str,
    key: str,
    loader: Callable[[], T],
    ttl_seconds: int,
    failure_value: T,
    failure_ttl_seconds: int = 60,
) -> T:
    cached = read_ttl_cache(cache, lock, key)
    if cached is not None:
        return cached
    key_lock = _key_lock(namespace, key)
    with key_lock:
        cached = read_ttl_cache(cache, lock, key)
        if cached is not None:
            return cached
        try:
            value = loader()
        except Exception:
            write_ttl_cache(cache, lock, key, failure_value, failure_ttl_seconds)
            raise
        write_ttl_cache(cache, lock, key, value, ttl_seconds)
        return value


def _key_lock(namespace: str, key: str) -> threading.Lock:
    lock_key = f"{namespace}:{key}"
    with _KEY_LOCKS_LOCK:
        return _KEY_LOCKS.setdefault(lock_key, threading.Lock())
