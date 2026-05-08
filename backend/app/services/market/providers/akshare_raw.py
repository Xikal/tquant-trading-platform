from __future__ import annotations

import threading
import time
import socket
from contextlib import contextmanager
import os

from app.core.config import get_settings


class AkshareRawClient:
    """Single raw AkShare boundary used by market providers.

    Business services must call Provider Router methods instead of importing or
    invoking AkShare directly. This client centralizes lock, retry, timeout and
    proxy behavior for provider adapters.
    """

    _LOCK_CATEGORIES = {
        "default",
        "spot_snapshot",
        "minute_bars",
        "limit_pool",
        "trade_dates",
        "market_breadth",
        "industry",
        "daily_history",
        "news",
        "notice",
        "emotion",
    }

    def __init__(self) -> None:
        self._locks: dict[str, threading.Lock] = {
            category: threading.Lock() for category in self._LOCK_CATEGORIES
        }
        self._locks_guard = threading.Lock()

    @contextmanager
    def _socket_timeout(self, timeout_seconds: float):
        previous_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(max(float(timeout_seconds or 0), 1.0))
        try:
            yield
        finally:
            socket.setdefaulttimeout(previous_timeout)

    @contextmanager
    def _no_proxy_env(self):
        proxy_keys = ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"]
        backup = {key: os.environ.get(key) for key in proxy_keys}
        try:
            for key in proxy_keys:
                os.environ.pop(key, None)
            yield
        finally:
            for key, value in backup.items():
                if value is not None:
                    os.environ[key] = value

    def _lock_for(self, purpose: str) -> threading.Lock:
        key = purpose if purpose in self._LOCK_CATEGORIES else "default"
        lock = self._locks.get(key)
        if lock is not None:
            return lock
        with self._locks_guard:
            return self._locks.setdefault(key, threading.Lock())

    def call(self, func, *args, purpose: str = "default", **kwargs):
        timeout_seconds = max(float(get_settings().akshare_timeout_seconds or 12), 3.0)
        with self._lock_for(purpose):
            with self._no_proxy_env():
                last_exc = None
                for attempt in range(3):
                    try:
                        with self._socket_timeout(timeout_seconds):
                            return func(*args, **kwargs)
                    except Exception as exc:
                        last_exc = exc
                        if attempt >= 2:
                            raise
                        time.sleep(0.6 * (attempt + 1))
                if last_exc is not None:
                    raise last_exc
                raise RuntimeError("akshare 调用失败")
