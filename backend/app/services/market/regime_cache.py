from __future__ import annotations

import time


def get_cached_snapshot(store: dict[str, tuple[float, object]], lock, key: str):
    with lock:
        cached = store.get(key)
        if cached is None:
            return None
        expires_at, payload = cached
        if expires_at <= time.monotonic():
            store.pop(key, None)
            return None
        return payload


def set_cached_snapshot(
    store: dict[str, tuple[float, object]],
    lock,
    *,
    ttl: float,
    key: str,
    payload: object,
) -> None:
    with lock:
        store[key] = (time.monotonic() + ttl, payload)
