from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import bff
from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.paper_auth import require_paper_trading
from app.models.schema_defs.bff import PaperWorkspaceBffResponse, StrategyWorkspaceBffResponse


def test_bff_manifest_exposes_versioned_frontend_contract() -> None:
    app = FastAPI()
    app.include_router(bff.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1,
        username="tester",
        is_active=True,
        roles="",
    )

    response = TestClient(app).get("/api/bff/v1/manifest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["api_version"] == "v1"
    assert payload["bff_version"] == "v1"
    assert "market" in payload["modules"]
    assert "strategy" in payload["modules"]


def test_paper_workspace_uses_bff_contract(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(bff.router, prefix="/api")
    user = SimpleNamespace(id=1, username="tester", is_active=True, roles="")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_paper_trading] = lambda: user
    app.dependency_overrides[get_db] = lambda: object()

    def fake_builder(*args, **kwargs):
        return PaperWorkspaceBffResponse(
            generated_at="2026-05-20 09:30:00",
            auto_trading_status={"running": False},
        )

    monkeypatch.setattr(bff, "build_paper_workspace", fake_builder)

    response = TestClient(app).get("/api/bff/v1/workspace/paper")

    assert response.status_code == 200
    payload = response.json()
    assert payload["api_version"] == "v1"
    assert payload["auto_trading_status"]["running"] is False


def test_strategy_workspace_uses_bff_contract(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(bff.router, prefix="/api")
    user = SimpleNamespace(id=1, username="tester", is_active=True, roles="")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: object()

    def fake_builder(*args, **kwargs):
        return StrategyWorkspaceBffResponse(generated_at="2026-05-20 09:30:00")

    monkeypatch.setattr(bff, "build_strategy_workspace", fake_builder)

    response = TestClient(app).get("/api/bff/v1/workspace/strategy")

    assert response.status_code == 200
    assert response.json()["api_version"] == "v1"
