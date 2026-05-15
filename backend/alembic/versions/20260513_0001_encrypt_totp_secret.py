"""encrypt stored TOTP secrets

Revision ID: 20260513_0001
Revises: 20260512_0001
Create Date: 2026-05-13 10:00:00
"""

from __future__ import annotations

import base64

import sqlalchemy as sa
from alembic import op
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

revision = "20260513_0001"
down_revision = "20260512_0001"
branch_labels = None
depends_on = None

_PREFIX = "enc:v1:"
_SALT = b"tquant-totp-secret-v1"
_INFO = b"tquant totp fernet"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        return
    columns = {item["name"] for item in inspector.get_columns("users")}
    if "mfa_totp_secret" not in columns:
        return
    _widen_secret_column()
    fernet = _fernet()
    _encrypt_existing_totp_secrets(bind, fernet)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        return
    columns = {item["name"] for item in inspector.get_columns("users")}
    if "mfa_totp_secret" not in columns:
        return
    encrypted_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM users WHERE mfa_totp_secret LIKE 'enc:v1:%'")
    ).scalar()
    if int(encrypted_count or 0) > 0:
        fernet = _fernet()
        _decrypt_existing_totp_secrets(bind, fernet)
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "mfa_totp_secret",
            existing_type=sa.String(length=255),
            type_=sa.String(length=80),
            existing_nullable=False,
            existing_server_default="",
        )


def _widen_secret_column() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "mfa_totp_secret",
            existing_type=sa.String(length=80),
            type_=sa.String(length=255),
            existing_nullable=False,
            existing_server_default="",
        )


def _encrypt_existing_totp_secrets(bind, fernet: Fernet) -> None:
    rows = bind.execute(
        sa.text(
            """
            SELECT id, mfa_totp_secret
            FROM users
            WHERE mfa_totp_secret IS NOT NULL
              AND mfa_totp_secret <> ''
              AND mfa_totp_secret NOT LIKE 'enc:v1:%'
            """
        )
    ).mappings()
    for row in rows:
        encrypted = _PREFIX + fernet.encrypt(str(row["mfa_totp_secret"]).encode("utf-8")).decode("ascii")
        bind.execute(sa.text("UPDATE users SET mfa_totp_secret = :secret WHERE id = :id"), {"secret": encrypted, "id": row["id"]})


def _decrypt_existing_totp_secrets(bind, fernet: Fernet) -> None:
    rows = bind.execute(
        sa.text(
            """
            SELECT id, mfa_totp_secret
            FROM users
            WHERE mfa_totp_secret LIKE 'enc:v1:%'
            """
        )
    ).mappings()
    for row in rows:
        encrypted = str(row["mfa_totp_secret"])[len(_PREFIX) :].encode("ascii")
        secret = fernet.decrypt(encrypted).decode("utf-8")
        bind.execute(sa.text("UPDATE users SET mfa_totp_secret = :secret WHERE id = :id"), {"secret": secret, "id": row["id"]})


def _fernet() -> Fernet:
    try:
        from app.core.config import get_settings

        configured = get_settings().auth_secret_key.strip()
    except Exception as exc:
        raise RuntimeError("AUTH_SECRET_KEY is required to migrate encrypted TOTP secrets") from exc
    if not configured:
        raise RuntimeError("AUTH_SECRET_KEY is required to migrate encrypted TOTP secrets")
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        info=_INFO,
    ).derive(configured.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(key))
