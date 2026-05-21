#!/usr/bin/env python3
from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from cryptography.fernet import Fernet, InvalidToken  # noqa: E402
from cryptography.hazmat.primitives import hashes  # noqa: E402
from cryptography.hazmat.primitives.kdf.hkdf import HKDF  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models.entities import SystemSetting  # noqa: E402

PREFIX = "enc:v1:"
SALT = b"tquant-secret-field-v1"
INFO = b"tquant secret field fernet"
SENSITIVE_KEYS = {"llm_api_key", "database_url"}


def main() -> int:
    settings = get_settings()
    old_key = (
        os.getenv("OLD_TQUANT_SETTINGS_ENCRYPTION_KEY", "").strip()
        or settings.auth_secret_key.strip()
    )
    new_key = (
        os.getenv("NEW_TQUANT_SETTINGS_ENCRYPTION_KEY", "").strip()
        or settings.tquant_settings_encryption_key.strip()
    )
    if not old_key or not new_key:
        print("OLD_TQUANT_SETTINGS_ENCRYPTION_KEY and NEW_TQUANT_SETTINGS_ENCRYPTION_KEY are required", file=sys.stderr)
        return 2

    old_fernet = _fernet(old_key)
    new_fernet = _fernet(new_key)
    updated = 0
    with SessionLocal() as db:
        try:
            rows = db.execute(select(SystemSetting).where(SystemSetting.key.in_(SENSITIVE_KEYS))).scalars().all()
            for row in rows:
                plaintext = _decrypt(row.value or "", old_fernet, new_fernet)
                if not plaintext:
                    continue
                row.value = PREFIX + new_fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")
                updated += 1
            db.commit()
        except Exception:
            db.rollback()
            raise
    print(f"reencrypted_settings={updated}")
    return 0


def _decrypt(value: str, old_fernet: Fernet, new_fernet: Fernet) -> str:
    clean = value.strip()
    if not clean:
        return ""
    if not clean.startswith(PREFIX):
        return clean
    token = clean[len(PREFIX) :].encode("ascii")
    for fernet in (old_fernet, new_fernet):
        try:
            return fernet.decrypt(token).decode("utf-8")
        except InvalidToken:
            continue
    raise InvalidToken("settings value cannot be decrypted with old or new key")


def _fernet(secret: str) -> Fernet:
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SALT,
        info=INFO,
    ).derive(secret.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(key))


if __name__ == "__main__":
    raise SystemExit(main())
