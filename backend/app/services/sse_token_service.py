from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from app.core.config import get_settings


@dataclass(frozen=True)
class SseStreamGrant:
    token: str
    user_id: int
    expires_at: float


class SseStreamTokenService:
    """Short-lived signed stream tokens that work across multiple web workers."""

    def __init__(self, ttl_seconds: int = 60, scope: str = "stream") -> None:
        self.ttl_seconds = ttl_seconds
        self.scope = scope

    def issue(self, user_id: int) -> SseStreamGrant:
        expires_at = time.time() + self.ttl_seconds
        payload = {
            "uid": int(user_id),
            "exp": expires_at,
            "nonce": secrets.token_urlsafe(12),
            "scope": self.scope,
            "v": 1,
        }
        token = self._encode(payload)
        grant = SseStreamGrant(
            token=token,
            user_id=user_id,
            expires_at=expires_at,
        )
        return grant

    def consume(self, token: str) -> int | None:
        payload = self._decode(token)
        if not payload:
            return None
        if str(payload.get("scope") or "") != self.scope:
            return None
        expires_at = float(payload.get("exp") or 0)
        if expires_at < time.time():
            return None
        try:
            return int(payload["uid"])
        except (KeyError, TypeError, ValueError):
            return None

    def _encode(self, payload: dict) -> str:
        payload_text = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        signature = _sign(payload_text)
        return f"{payload_text}.{signature}"

    def _decode(self, token: str) -> dict | None:
        try:
            payload_text, signature = token.split(".", 1)
        except ValueError:
            return None
        if not hmac.compare_digest(signature, _sign(payload_text)):
            return None
        try:
            decoded = json.loads(_b64decode(payload_text).decode("utf-8"))
        except (ValueError, TypeError, UnicodeDecodeError):
            return None
        return decoded if isinstance(decoded, dict) else None


def _secret() -> bytes:
    configured = get_settings().auth_secret_key.strip()
    if not configured:
        raise ValueError("AUTH_SECRET_KEY 未配置，无法签发实时流令牌")
    return hashlib.sha256(configured.encode("utf-8")).digest()


def _sign(payload_text: str) -> str:
    return _b64encode(hmac.new(_secret(), payload_text.encode("ascii"), hashlib.sha256).digest())


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))
