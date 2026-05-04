from __future__ import annotations

from collections import defaultdict, deque
import ipaddress
from pathlib import Path
import sqlite3
import time
from threading import Lock

from fastapi import HTTPException, Request, status


class InMemorySlidingWindowRateLimiter:
    """In-process sliding window limiter.

    The limiter intentionally avoids SQLite writes on hot paths; production
    abuse protection should still live at the reverse proxy or gateway layer.
    """

    def __init__(self, *, namespace: str, max_calls: int, window_seconds: int) -> None:
        self.namespace = namespace
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._lock = Lock()
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] < cutoff:
                events.popleft()
            if len(events) >= self.max_calls:
                return False
            events.append(now)
            return True

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


class SQLiteSlidingWindowRateLimiter:
    """Cross-worker sliding window limiter backed by a local SQLite file."""

    def __init__(self, *, namespace: str, max_calls: int, window_seconds: int) -> None:
        self.namespace = namespace
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._lock = Lock()
        self._fallback = InMemorySlidingWindowRateLimiter(
            namespace=namespace,
            max_calls=max_calls,
            window_seconds=window_seconds,
        )
        self._db_path = _rate_limit_db_path()
        self._ensure_schema()

    def allow(self, key: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        try:
            with self._lock, sqlite3.connect(self._db_path, timeout=0.2) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute(
                    "DELETE FROM rate_limit_events WHERE namespace = ? AND client_key = ? AND created_at < ?",
                    (self.namespace, key, cutoff),
                )
                count = conn.execute(
                    "SELECT COUNT(*) FROM rate_limit_events WHERE namespace = ? AND client_key = ? AND created_at >= ?",
                    (self.namespace, key, cutoff),
                ).fetchone()[0]
                if count >= self.max_calls:
                    return False
                conn.execute(
                    "INSERT INTO rate_limit_events(namespace, client_key, created_at) VALUES (?, ?, ?)",
                    (self.namespace, key, now),
                )
                return True
        except sqlite3.Error:
            return self._fallback.allow(key)

    def clear(self) -> None:
        self._fallback.clear()
        try:
            with self._lock, sqlite3.connect(self._db_path, timeout=0.5) as conn:
                conn.execute("DELETE FROM rate_limit_events WHERE namespace = ?", (self.namespace,))
        except sqlite3.Error:
            return

    def _ensure_schema(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._lock, sqlite3.connect(self._db_path, timeout=1.0) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS rate_limit_events (
                        namespace TEXT NOT NULL,
                        client_key TEXT NOT NULL,
                        created_at REAL NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_rate_limit_namespace_key_time
                    ON rate_limit_events(namespace, client_key, created_at)
                    """
                )
        except sqlite3.Error:
            return


def _rate_limit_db_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "rate_limit.sqlite3"


# Keep the global limiter in-process. It is a coarse abuse guard on a very hot
# path; durable/global request throttling should live at Nginx or the gateway.
_global_limiter = InMemorySlidingWindowRateLimiter(namespace="global", max_calls=30, window_seconds=1)
_ai_decision_limiter = SQLiteSlidingWindowRateLimiter(namespace="ai_decision", max_calls=30, window_seconds=60)
_auth_login_limiter = SQLiteSlidingWindowRateLimiter(namespace="auth_login", max_calls=30, window_seconds=60)
_auth_register_limiter = SQLiteSlidingWindowRateLimiter(namespace="auth_register", max_calls=30, window_seconds=3600)


def is_global_rate_allowed(request: Request) -> bool:
    path = request.url.path
    if path.startswith("/assets/") or path.endswith((".js", ".css", ".png", ".svg", ".ico")):
        return True
    return _global_limiter.allow(_client_key(request))


def require_ai_decision_rate_limit(request: Request) -> None:
    if _ai_decision_limiter.allow(_client_key(request)):
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="AI 解读请求过于频繁，请稍后再试。",
    )


def require_auth_login_rate_limit(request: Request) -> None:
    if _auth_login_limiter.allow(_client_key(request)):
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="登录请求过于频繁，请稍后再试。",
    )


def require_auth_register_rate_limit(request: Request) -> None:
    if _auth_register_limiter.allow(_client_key(request)):
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="注册请求过于频繁，请稍后再试。",
    )


def _client_key(request: Request) -> str:
    client_host = request.client.host if request.client else ""
    if _is_trusted_proxy_host(client_host):
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip", "").strip()
        if _looks_like_ip(forwarded):
            return forwarded
        if _looks_like_ip(real_ip):
            return real_ip
    return client_host or "unknown"


def _is_trusted_proxy_host(host: str) -> bool:
    if not host:
        return False
    if host == "testclient":
        return False
    try:
        parsed = ipaddress.ip_address(host)
    except ValueError:
        return False
    return parsed.is_loopback or parsed.is_private


def _looks_like_ip(value: str) -> bool:
    if not value:
        return False
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def clear_rate_limit_events() -> None:
    """Test/maintenance helper to clear limiter state."""

    for limiter in (_global_limiter, _ai_decision_limiter, _auth_login_limiter, _auth_register_limiter):
        limiter.clear()
