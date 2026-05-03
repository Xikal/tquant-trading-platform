from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class SseStreamGrant:
    token: str
    user_id: int
    expires_at: float


class SseStreamTokenService:
    """Short-lived one-time stream tokens for EventSource connections."""

    def __init__(self, ttl_seconds: int = 60) -> None:
        self.ttl_seconds = ttl_seconds
        self._lock = Lock()
        self._tokens: dict[str, SseStreamGrant] = {}

    def issue(self, user_id: int) -> SseStreamGrant:
        self._prune()
        token = secrets.token_urlsafe(32)
        grant = SseStreamGrant(
            token=token,
            user_id=user_id,
            expires_at=time.time() + self.ttl_seconds,
        )
        with self._lock:
            self._tokens[token] = grant
        return grant

    def consume(self, token: str) -> int | None:
        self._prune()
        with self._lock:
            grant = self._tokens.pop(token, None)
        if grant is None or grant.expires_at < time.time():
            return None
        return grant.user_id

    def _prune(self) -> None:
        now = time.time()
        with self._lock:
            expired = [token for token, grant in self._tokens.items() if grant.expires_at < now]
            for token in expired:
                self._tokens.pop(token, None)
