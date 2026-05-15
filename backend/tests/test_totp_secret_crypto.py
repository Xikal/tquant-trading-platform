from __future__ import annotations

from types import SimpleNamespace

from app.services import totp_secret_crypto


def test_fernet_cache_is_cleared_when_auth_secret_rotates(monkeypatch) -> None:
    current = {"value": "secret-a"}

    monkeypatch.setattr(
        totp_secret_crypto,
        "get_settings",
        lambda: SimpleNamespace(auth_secret_key=current["value"]),
    )
    totp_secret_crypto._FERNET_SECRET_HASH = ""
    totp_secret_crypto._fernet_for_secret.cache_clear()

    totp_secret_crypto._fernet()
    assert totp_secret_crypto._fernet_for_secret.cache_info().currsize == 1

    current["value"] = "secret-b"
    totp_secret_crypto._fernet()

    assert totp_secret_crypto._fernet_for_secret.cache_info().currsize == 1
