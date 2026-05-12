from __future__ import annotations

import time
import uuid

import redis

_SLIDING_WINDOW_SCRIPT = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ARGV[1])
local count = redis.call('ZCARD', KEYS[1])
if count >= tonumber(ARGV[2]) then
  return 0
end
redis.call('ZADD', KEYS[1], ARGV[3], ARGV[4])
redis.call('EXPIRE', KEYS[1], ARGV[5])
return 1
"""


class RedisSlidingWindowRateLimiter:
    """Cross-process sliding window limiter backed by Redis sorted sets."""

    def __init__(self, *, redis_url: str, namespace: str, max_calls: int, window_seconds: int, fail_closed: bool = True) -> None:
        self.namespace = namespace
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.fail_closed = fail_closed
        self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    def allow(self, key: str) -> bool:
        now = time.time()
        redis_key = f"tquant:rate:{self.namespace}:{key}"
        try:
            allowed = self._client.eval(
                _SLIDING_WINDOW_SCRIPT,
                1,
                redis_key,
                now - self.window_seconds,
                self.max_calls,
                now,
                f"{now:.6f}:{uuid.uuid4().hex}",
                max(self.window_seconds * 2, 1),
            )
            return bool(int(allowed))
        except redis.RedisError:
            return not self.fail_closed

    def clear(self) -> None:
        pattern = f"tquant:rate:{self.namespace}:*"
        try:
            for key in self._client.scan_iter(pattern, count=200):
                self._client.delete(key)
        except redis.RedisError:
            return
