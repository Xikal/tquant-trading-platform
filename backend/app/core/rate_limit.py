from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status


class SlidingWindowRateLimiter:
    def __init__(self, *, max_calls: int, window_seconds: int) -> None:
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._lock = Lock()
        self._calls: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            calls = self._calls[key]
            while calls and calls[0] < cutoff:
                calls.popleft()
            if len(calls) >= self.max_calls:
                return False
            calls.append(now)
            return True


_global_limiter = SlidingWindowRateLimiter(max_calls=30, window_seconds=1)
_ai_decision_limiter = SlidingWindowRateLimiter(max_calls=30, window_seconds=60)
_auth_login_limiter = SlidingWindowRateLimiter(max_calls=5, window_seconds=60)
_auth_register_limiter = SlidingWindowRateLimiter(max_calls=3, window_seconds=3600)


def is_global_rate_allowed(request: Request) -> bool:
    if _is_test_client(request):
        return True
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
    if _is_test_client(request):
        return
    if _auth_login_limiter.allow(_client_key(request)):
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="登录请求过于频繁，请稍后再试。",
    )


def require_auth_register_rate_limit(request: Request) -> None:
    if _is_test_client(request):
        return
    if _auth_register_limiter.allow(_client_key(request)):
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="注册请求过于频繁，请稍后再试。",
    )


def _client_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip", "").strip()
    client_host = request.client.host if request.client else ""
    return forwarded_for or real_ip or client_host or "unknown"


def _is_test_client(request: Request) -> bool:
    return bool(request.client and request.client.host == "testclient")
