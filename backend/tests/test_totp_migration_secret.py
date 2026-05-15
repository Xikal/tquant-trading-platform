from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core import config


def _load_revision_module():
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "20260513_0001_encrypt_totp_secret.py"
    spec = importlib.util.spec_from_file_location("totp_secret_revision", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_totp_migration_requires_configured_auth_secret(monkeypatch) -> None:
    module = _load_revision_module()
    monkeypatch.setattr(config, "get_settings", lambda: SimpleNamespace(auth_secret_key=""))

    with pytest.raises(RuntimeError, match="AUTH_SECRET_KEY"):
        module._fernet()
