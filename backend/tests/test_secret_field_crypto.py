from __future__ import annotations

from types import SimpleNamespace

from app.services import secret_field_crypto


def test_secret_field_crypto_uses_settings_key_for_new_values(monkeypatch) -> None:
    monkeypatch.setattr(
        secret_field_crypto,
        "get_settings",
        lambda: SimpleNamespace(
            auth_secret_key="auth-secret-0123456789abcdef0123456789abcdef0123456789abcdef",
            tquant_settings_encryption_key="settings-secret-0123456789abcdef0123456789abcdef0123456789abcdef",
        ),
    )
    secret_field_crypto._fernet_for_secret.cache_clear()

    encrypted = secret_field_crypto.encrypt_secret_field("sk-test")

    assert encrypted.startswith(secret_field_crypto.PREFIX)
    assert secret_field_crypto.decrypt_secret_field(encrypted) == "sk-test"


def test_secret_field_crypto_can_decrypt_legacy_auth_key_values(monkeypatch) -> None:
    current = {
        "auth_secret_key": "legacy-auth-secret-0123456789abcdef0123456789abcdef0123456789abcdef",
        "tquant_settings_encryption_key": "",
    }
    monkeypatch.setattr(secret_field_crypto, "get_settings", lambda: SimpleNamespace(**current))
    secret_field_crypto._fernet_for_secret.cache_clear()
    legacy = secret_field_crypto.encrypt_secret_field("mysql://legacy-secret")

    current["tquant_settings_encryption_key"] = (
        "new-settings-secret-0123456789abcdef0123456789abcdef0123456789abcdef"
    )

    assert secret_field_crypto.decrypt_secret_field(legacy) == "mysql://legacy-secret"
