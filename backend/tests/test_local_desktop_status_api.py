from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import local_desktop
from app.core.database import get_db
from app.models.schema_defs.local_desktop import (
    LocalDesktopComponentStatus,
    LocalDesktopDirectoryStatus,
    LocalDesktopStatusResponse,
)


def test_local_desktop_status_api_is_public_read_only(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(local_desktop.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()
    monkeypatch.setattr(
        local_desktop,
        "build_local_desktop_status",
        lambda db: LocalDesktopStatusResponse(
            generated_at=datetime(2026, 6, 13, 10, 0),
            app="TQuant",
            environment="local",
            version="test",
            components=[LocalDesktopComponentStatus(name="backend", status="ok")],
            directories=[LocalDesktopDirectoryStatus(key="logs", path="/tmp/logs", exists=False)],
            launch_guides=[],
            safety={
                "deploy_allowed": False,
                "restart_production_allowed": False,
                "cleanup_allowed": False,
                "auto_trade_allowed": False,
                "strategy_mutation_allowed": False,
            },
        ),
    )

    response = TestClient(app).get("/api/local/status")

    assert response.status_code == 200
    body = response.json()
    assert body["components"][0]["name"] == "backend"
    assert body["safety"]["deploy_allowed"] is False


def test_local_desktop_status_api_does_not_return_secrets(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(local_desktop.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()
    monkeypatch.setattr(
        local_desktop,
        "build_local_desktop_status",
        lambda db: LocalDesktopStatusResponse(
            generated_at=datetime(2026, 6, 13, 10, 0),
            app="TQuant",
            environment="local",
            components=[LocalDesktopComponentStatus(name="mysql", status="error", message="database unavailable")],
            directories=[],
            launch_guides=[],
            safety={},
        ),
    )

    response = TestClient(app).get("/api/local/status")
    text = response.text.lower()

    assert response.status_code == 200
    assert "password" not in text
    assert "secret" not in text
    assert "token" not in text
