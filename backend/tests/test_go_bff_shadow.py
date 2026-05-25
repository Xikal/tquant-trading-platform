from __future__ import annotations

from types import SimpleNamespace

from fastapi import BackgroundTasks

from app.models.schema_defs.bff import BffManifestResponse, BffWorkspaceManifest, PaperWorkspaceBffResponse
from app.services.bff import go_gateway_shadow


def test_go_bff_shadow_disabled_by_default(monkeypatch) -> None:
    called = False

    def fake_remote(*args, **kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(go_gateway_shadow, "get_settings", lambda: SimpleNamespace(tquant_bff_gateway_url="", tquant_bff_shadow_enabled=False))
    monkeypatch.setattr(go_gateway_shadow, "remote_bff_get", fake_remote)

    tasks = BackgroundTasks()
    scheduled = go_gateway_shadow.schedule_go_bff_shadow_check(
        tasks,
        workspace="paper",
        response_model=PaperWorkspaceBffResponse,
        local_payload=PaperWorkspaceBffResponse(generated_at="2026-05-23 10:00:00"),
    )

    assert scheduled is False
    assert called is False
    assert tasks.tasks == []


def test_go_bff_manifest_shadow_schedules_and_uses_manifest_path(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        go_gateway_shadow,
        "get_settings",
        lambda: SimpleNamespace(
            tquant_bff_gateway_url="http://go-bff-gateway:8091",
            tquant_bff_shadow_enabled=True,
            tquant_internal_service_token="internal-secret",
        ),
    )

    def fake_remote(base_url, path, *, params=None, forward_headers=None):
        captured["base_url"] = base_url
        captured["path"] = path
        captured["params"] = params
        captured["forward_headers"] = dict(forward_headers or {})
        return {
            "api_version": "v1",
            "bff_version": "v1",
            "schema_version": "v13",
            "gateway_prefix": "/api",
            "modules": ["auth", "market"],
            "workspaces": {
                "paper": {"path": "/api/bff/v1/workspace/paper", "schema_version": "v13", "model": "PaperWorkspaceBffResponse"},
            },
        }

    monkeypatch.setattr(go_gateway_shadow, "remote_bff_get", fake_remote)

    tasks = BackgroundTasks()
    scheduled = go_gateway_shadow.schedule_go_bff_shadow_check(
        tasks,
        workspace="manifest",
        response_model=BffManifestResponse,
        local_payload=BffManifestResponse(
            modules=["auth", "market"],
            workspaces={
                "paper": BffWorkspaceManifest(
                    path="/api/bff/v1/workspace/paper",
                    schema_version="v13",
                    model="PaperWorkspaceBffResponse",
                )
            },
        ),
        request_headers={"Authorization": "Bearer user-token"},
    )

    assert scheduled is True
    assert len(tasks.tasks) == 1
    tasks.tasks[0].func(*tasks.tasks[0].args, **tasks.tasks[0].kwargs)
    assert captured["path"] == "/api/bff/v1/manifest"
    assert captured["forward_headers"]["Authorization"] == "Bearer user-token"


def test_go_bff_workspace_shadow_uses_workspace_path(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        go_gateway_shadow,
        "get_settings",
        lambda: SimpleNamespace(
            tquant_bff_gateway_url="http://go-bff-gateway:8091",
            tquant_bff_shadow_enabled=True,
            tquant_internal_service_token="internal-secret",
        ),
    )

    def fake_remote(base_url, path, *, params=None, forward_headers=None):
        captured["path"] = path
        captured["params"] = params
        return {
            "api_version": "v1",
            "schema_version": "v13",
            "generated_at": "2026-05-23 10:00:00",
            "account": None,
            "positions": [],
            "orders": [],
            "trades": [],
            "stock_pnl": None,
            "performance": None,
            "sector_etf_t0_performance": None,
            "strategy_performance": [],
            "market_performance": [],
            "tag_performance": [],
            "risk_events": [],
            "auto_trading_status": {},
            "auto_trading_runs": [],
            "partial_errors": [],
        }

    monkeypatch.setattr(go_gateway_shadow, "remote_bff_get", fake_remote)

    tasks = BackgroundTasks()
    scheduled = go_gateway_shadow.schedule_go_bff_shadow_check(
        tasks,
        workspace="paper",
        response_model=PaperWorkspaceBffResponse,
        local_payload=PaperWorkspaceBffResponse(generated_at="2026-05-23 10:00:00"),
        params={"order_limit": 5},
    )

    assert scheduled is True
    assert len(tasks.tasks) == 1
    tasks.tasks[0].func(*tasks.tasks[0].args, **tasks.tasks[0].kwargs)
    assert captured["path"] == "/api/bff/v1/workspace/paper"
    assert captured["params"] == {"order_limit": 5}
