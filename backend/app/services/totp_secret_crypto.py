from __future__ import annotations

import base64
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import get_settings

_PREFIX = "enc:v1:"
_SALT = b"tquant-totp-secret-v1"
_INFO = b"tquant totp fernet"


def is_encrypted_totp_secret(value: str | None) -> bool:
    return bool((value or "").startswith(_PREFIX))


def encrypt_totp_secret(secret: str | None) -> str:
    clean = (secret or "").strip()
    if not clean or is_encrypted_totp_secret(clean):
        return clean
    encrypted = _fernet().encrypt(clean.encode("utf-8")).decode("ascii")
    return f"{_PREFIX}{encrypted}"


def decrypt_totp_secret(value: str | None) -> str:
    clean = (value or "").strip()
    if not clean:
        return ""
    if not is_encrypted_totp_secret(clean):
        return clean
    token = clean[len(_PREFIX) :].encode("ascii")
    try:
        return _fernet().decrypt(token).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("TOTP 密钥无法解密，请重新绑定动态验证码") from exc


def _fernet() -> Fernet:
    configured = get_settings().auth_secret_key.strip()
    if not configured:
        raise ValueError("AUTH_SECRET_KEY 未配置，无法加密 TOTP 密钥")
    return _fernet_for_secret(configured)


@lru_cache(maxsize=4)
def _fernet_for_secret(configured: str) -> Fernet:
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        info=_INFO,
    ).derive(configured.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(key))
