"""encrypt sensitive system settings

Revision ID: 20260519_0002_encrypt_settings
Revises: 20260519_0001_auth_hardening
Create Date: 2026-05-19
"""

from __future__ import annotations

import base64

import sqlalchemy as sa
from alembic import op
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

revision = "20260519_0002_encrypt_settings"
down_revision = "20260519_0001_auth_hardening"
branch_labels = None
depends_on = None

_PREFIX = "enc:v1:"
_SALT = b"tquant-secret-field-v1"
_INFO = b"tquant secret field fernet"
_SENSITIVE_KEYS = ("llm_api_key", "database_url")


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind):
        return
    fernet = _fernet()
    for key in _SENSITIVE_KEYS:
        rows = bind.execute(
            sa.text(
                """
                SELECT id, value FROM system_settings
                WHERE `key` = :key AND value IS NOT NULL AND value <> '' AND value NOT LIKE 'enc:v1:%'
                """
            ),
            {"key": key},
        ).mappings()
        for row in rows:
            encrypted = _PREFIX + fernet.encrypt(str(row["value"]).encode("utf-8")).decode("ascii")
            bind.execute(sa.text("UPDATE system_settings SET value = :value WHERE id = :id"), {"value": encrypted, "id": row["id"]})


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind):
        return
    fernet = _fernet()
    for key in _SENSITIVE_KEYS:
        rows = bind.execute(
            sa.text("SELECT id, value FROM system_settings WHERE `key` = :key AND value LIKE 'enc:v1:%'"),
            {"key": key},
        ).mappings()
        for row in rows:
            token = str(row["value"])[len(_PREFIX) :].encode("ascii")
            decrypted = fernet.decrypt(token).decode("utf-8")
            bind.execute(sa.text("UPDATE system_settings SET value = :value WHERE id = :id"), {"value": decrypted, "id": row["id"]})


def _table_exists(bind) -> bool:
    return "system_settings" in sa.inspect(bind).get_table_names()


def _fernet() -> Fernet:
    try:
        from app.core.config import get_settings

        configured = get_settings().auth_secret_key.strip()
    except Exception as exc:
        raise RuntimeError("AUTH_SECRET_KEY is required to migrate encrypted settings") from exc
    if not configured:
        raise RuntimeError("AUTH_SECRET_KEY is required to migrate encrypted settings")
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        info=_INFO,
    ).derive(configured.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(key))
