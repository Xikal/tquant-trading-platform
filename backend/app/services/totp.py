from __future__ import annotations

import base64
import hmac
import secrets
import struct
import time
from hashlib import sha1
from urllib.parse import quote, urlencode


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def build_otpauth_uri(*, issuer: str, username: str, secret: str) -> str:
    label = f"{issuer}:{username}"
    query = urlencode(
        {
            "secret": secret,
            "issuer": issuer,
            "algorithm": "SHA1",
            "digits": "6",
            "period": "30",
        }
    )
    return f"otpauth://totp/{quote(label, safe='')}?{query}"


def verify_totp(code: str, secret: str, *, window: int = 1, now: int | None = None) -> bool:
    cleaned = "".join(ch for ch in str(code or "") if ch.isdigit())
    if len(cleaned) != 6 or not secret:
        return False
    timestamp = int(now if now is not None else time.time())
    counter = timestamp // 30
    return any(hmac.compare_digest(cleaned, _totp_at(secret, counter + offset)) for offset in range(-window, window + 1))


def generate_totp_code(secret: str, *, now: int | None = None) -> str:
    timestamp = int(now if now is not None else time.time())
    return _totp_at(secret, timestamp // 30)


def _totp_at(secret: str, counter: int) -> str:
    padded = secret + "=" * (-len(secret) % 8)
    key = base64.b32decode(padded, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", int(counter)), sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{binary % 1_000_000:06d}"
