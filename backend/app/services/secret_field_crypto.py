from __future__ import annotations

import base64
import threading
from functools import lru_cache

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import get_settings

PREFIX = "enc:v1:"
_SALT = b"tquant-secret-field-v1"
_INFO = b"tquant secret field fernet"
_FERNET_CACHE_LOCK = threading.Lock()
_FERNET_SECRET = ""


def is_encrypted_secret_field(value: str | None) -> bool:
    return bool((value or "").strip().startswith(PREFIX))


def encrypt_secret_field(value: str | None) -> str:
    clean = (value or "").strip()
    if not clean or is_encrypted_secret_field(clean):
        return clean
    return PREFIX + _fernet().encrypt(clean.encode("utf-8")).decode("ascii")


def decrypt_secret_field(value: str | None) -> str:
    clean = (value or "").strip()
    if not is_encrypted_secret_field(clean):
        return clean
    token = clean[len(PREFIX) :].encode("ascii")
    return _fernet().decrypt(token).decode("utf-8")


def _fernet() -> Fernet:
    configured = get_settings().auth_secret_key.strip()
    if not configured:
        raise ValueError("AUTH_SECRET_KEY 未配置，无法加密敏感配置")
    _clear_cache_if_secret_rotated(configured)
    return _fernet_for_secret(configured)


def _clear_cache_if_secret_rotated(configured: str) -> None:
    global _FERNET_SECRET
    with _FERNET_CACHE_LOCK:
        if _FERNET_SECRET and _FERNET_SECRET != configured:
            _fernet_for_secret.cache_clear()
        _FERNET_SECRET = configured


@lru_cache(maxsize=4)
def _fernet_for_secret(configured: str) -> Fernet:
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        info=_INFO,
    ).derive(configured.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(key))
