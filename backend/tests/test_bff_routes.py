from __future__ import annotations

import logging
import time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.routes import bff
from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.paper_auth import require_paper_trading
from app.models.schema_defs.bff import (
    MonitorWorkspaceBffResponse,
    PaperWorkspaceBffResponse,
    SettingsWorkspaceBffResponse,
    StrategyWorkspaceBffResponse,
)
from app.models.schema_defs.market import MarketBreadthResponse, SectorRelativeStrengthResponse
from app.services.bff import remote_adapters, remote_client
from app.services.bff import workspace_cache


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
    assert payload["schema_version"] == "v14"
    assert "market" in payload["modules"]
    assert "strategy" in payload["modules"]
    assert "settings" in payload["modules"]
    assert payload["workspaces"]["strategy"]["schema_version"] == "v14"
    assert payload["workspaces"]["paper"]["path"] == "/api/bff/v1/workspace/paper"


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
    assert payload["schema_version"] == "v14"
    assert payload["auto_trading_status"]["running"] is False


def test_paper_workspace_timeout_returns_partial_payload(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(bff.router, prefix="/api")
    user = SimpleNamespace(id=1, username="tester", is_active=True, roles="")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_paper_trading] = lambda: user
    app.dependency_overrides[get_db] = lambda: object()
    monkeypatch.setattr(
        bff,
        "get_settings",
        lambda: SimpleNamespace(
            bff_workspace_timeout_seconds=0.01,
            tquant_internal_service_token="",
        ),
    )

    def slow_builder(*args, **kwargs):
        time.sleep(0.05)
        return PaperWorkspaceBffResponse(generated_at="2026-05-20 09:30:00")

    monkeypatch.setattr(bff, "build_paper_workspace", slow_builder)

    response = TestClient(app).get("/api/bff/v1/workspace/paper")

    assert response.status_code == 200
    payload = response.json()
    assert payload["partial_errors"][0]["source"] == "paper_workspace"


def test_monitor_workspace_builder_errors_return_partial_payload(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(bff.router, prefix="/api")
    user = SimpleNamespace(id=1, username="tester", is_active=True, roles="")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: object()
    monkeypatch.setattr(bff, "get_settings", lambda: SimpleNamespace(tquant_internal_service_token=""))
    monkeypatch.setattr(
        workspace_cache,
        "get_settings",
        lambda: SimpleNamespace(
            bff_workspace_cache_enabled=False,
            bff_monitor_cache_ttl_seconds=0,
            bff_paper_cache_ttl_seconds=0,
            bff_strategy_cache_ttl_seconds=0,
            bff_settings_cache_ttl_seconds=0,
        ),
    )

    monkeypatch.setattr(bff, "build_monitor_snapshot", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")))
    monkeypatch.setattr(bff, "market_breadth", lambda *args, **kwargs: MarketBreadthResponse(updated_at="2026-05-25 10:00:00"))
    monkeypatch.setattr(bff, "sector_relative_strength", lambda *args: SectorRelativeStrengthResponse(updated_at="2026-05-25 10:00:00"))
    monkeypatch.setattr(bff, "build_market_review_summary", lambda *args, **kwargs: (None, []))
    monkeypatch.setattr(bff, "paired_hedge_research", lambda *args: {"updated_at": "2026-05-25 10:00:00", "ideas": []})

    response = TestClient(app).get("/api/bff/v1/workspace/monitor")

    assert response.status_code == 200
    payload = response.json()
    assert payload["monitor_snapshot"] is None
    assert payload["market_breadth"] is not None
    assert payload["partial_errors"][0]["source"] == "monitor_snapshot"


def test_monitor_workspace_uses_fast_breadth_without_workspace_timeout(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(bff.router, prefix="/api")
    user = SimpleNamespace(id=1, username="tester", is_active=True, roles="")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: object()
    monkeypatch.setattr(
        bff,
        "get_settings",
        lambda: SimpleNamespace(
            bff_workspace_timeout_seconds=0.01,
            tquant_internal_service_token="",
        ),
    )
    monkeypatch.setattr(
        workspace_cache,
        "get_settings",
        lambda: SimpleNamespace(
            bff_workspace_cache_enabled=False,
            bff_monitor_cache_ttl_seconds=0,
            bff_paper_cache_ttl_seconds=0,
            bff_strategy_cache_ttl_seconds=0,
            bff_settings_cache_ttl_seconds=0,
        ),
    )
    calls: dict[str, object] = {}

    monkeypatch.setattr(
        bff,
        "build_monitor_snapshot",
        lambda *args, **kwargs: {"updated_at": "2026-05-25 10:00:00"},
    )

    def fake_market_breadth(*, realtime=True, db):
        calls["realtime"] = realtime
        return MarketBreadthResponse(updated_at="2026-05-25 10:00:00", state="neutral")

    monkeypatch.setattr(bff, "market_breadth", fake_market_breadth)
    monkeypatch.setattr(
        bff,
        "sector_relative_strength",
        lambda *args: SectorRelativeStrengthResponse(updated_at="2026-05-25 10:00:00"),
    )
    monkeypatch.setattr(bff, "build_market_review_summary", lambda *args, **kwargs: (None, []))
    monkeypatch.setattr(bff, "paired_hedge_research", lambda *args: {"updated_at": "2026-05-25 10:00:00", "ideas": []})

    response = TestClient(app).get("/api/bff/v1/workspace/monitor")

    assert response.status_code == 200
    payload = response.json()
    assert payload["monitor_snapshot"]["updated_at"] == "2026-05-25 10:00:00"
    assert payload["market_breadth"]["state"] == "neutral"
    assert payload["partial_errors"] == []
    assert calls["realtime"] is False


def test_paper_workspace_can_use_remote_adapter(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(bff.router, prefix="/api")
    user = SimpleNamespace(id=1, username="tester", is_active=True, roles="")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_paper_trading] = lambda: user
    app.dependency_overrides[get_db] = lambda: object()

    def fake_remote(*args, **kwargs):
        return PaperWorkspaceBffResponse(
            generated_at="2026-05-20 09:31:00",
            auto_trading_status={"source": "remote"},
        )

    def forbidden_local(*args, **kwargs):
        raise AssertionError("local fallback should not run when remote adapter succeeds")

    monkeypatch.setattr(bff, "load_remote_paper_workspace", fake_remote)
    monkeypatch.setattr(bff, "build_paper_workspace", forbidden_local)

    response = TestClient(app).get("/api/bff/v1/workspace/paper", headers={"Authorization": "Bearer test"})

    assert response.status_code == 200
    assert response.json()["auto_trading_status"]["source"] == "remote"


def test_bff_hop_header_forces_local_fallback(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(bff.router, prefix="/api")
    user = SimpleNamespace(id=1, username="tester", is_active=True, roles="")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_paper_trading] = lambda: user
    app.dependency_overrides[get_db] = lambda: object()

    def forbidden_remote(*args, **kwargs):
        raise AssertionError("remote adapter should not run on a BFF hop request")

    def fake_builder(*args, **kwargs):
        return PaperWorkspaceBffResponse(
            generated_at="2026-05-20 09:32:00",
            auto_trading_status={"source": "local"},
        )

    monkeypatch.setattr(bff, "load_remote_paper_workspace", forbidden_remote)
    monkeypatch.setattr(bff, "build_paper_workspace", fake_builder)
    monkeypatch.setattr(bff, "get_settings", lambda: SimpleNamespace(tquant_internal_service_token="internal-secret"))

    response = TestClient(app).get(
        "/api/bff/v1/workspace/paper",
        headers={"X-TQuant-Bff-Hop": "1", "X-Internal-Service-Token": "internal-secret"},
    )

    assert response.status_code == 200
    assert response.json()["auto_trading_status"]["source"] == "local"


def test_forged_bff_hop_header_does_not_skip_remote(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(bff.router, prefix="/api")
    user = SimpleNamespace(id=1, username="tester", is_active=True, roles="")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_paper_trading] = lambda: user
    app.dependency_overrides[get_db] = lambda: object()

    monkeypatch.setattr(bff, "get_settings", lambda: SimpleNamespace(tquant_internal_service_token="internal-secret"))
    monkeypatch.setattr(
        bff,
        "load_remote_paper_workspace",
        lambda *args, **kwargs: PaperWorkspaceBffResponse(
            generated_at="2026-05-20 09:33:00",
            auto_trading_status={"source": "remote"},
        ),
    )

    response = TestClient(app).get("/api/bff/v1/workspace/paper", headers={"X-TQuant-Bff-Hop": "1"})

    assert response.status_code == 200
    assert response.json()["auto_trading_status"]["source"] == "remote"


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


def test_settings_workspace_uses_bff_contract(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(bff.router, prefix="/api")
    user = SimpleNamespace(id=1, username="tester", is_active=True, roles="")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: object()

    def fake_builder(*args, **kwargs):
        return SettingsWorkspaceBffResponse(generated_at="2026-05-20 09:30:00", admin_enabled=False)

    monkeypatch.setattr(bff, "build_settings_workspace", fake_builder)

    response = TestClient(app).get("/api/bff/v1/workspace/settings")

    assert response.status_code == 200
    assert response.json()["api_version"] == "v1"


def test_remote_adapter_schema_mismatch_falls_back(monkeypatch, caplog) -> None:
    monkeypatch.setattr(
        remote_adapters,
        "get_settings",
        lambda: SimpleNamespace(tquant_trade_service_url="http://trade-service"),
    )
    monkeypatch.setattr(remote_adapters, "remote_bff_get", lambda *args, **kwargs: {"api_version": "v1", "schema_version": "v99"})
    opened: list[str] = []
    monkeypatch.setattr(remote_adapters, "open_remote_bff_circuit", lambda base_url: opened.append(base_url))

    with caplog.at_level(logging.WARNING):
        result = remote_adapters.load_remote_paper_workspace(order_limit=1, trade_limit=1, run_limit=1)

    assert result is None
    assert opened == ["http://trade-service"]
    assert "schema_version=v99" in caplog.text
    assert "missing_fields" in caplog.text


def test_remote_client_does_not_forward_credentials_to_untrusted_http(monkeypatch) -> None:
    remote_client._CIRCUIT_OPEN_UNTIL.clear()
    monkeypatch.setattr(
        remote_client,
        "get_settings",
        lambda: SimpleNamespace(
            tquant_service_call_timeout_seconds=1.0,
            tquant_service_circuit_breaker_seconds=30.0,
            tquant_internal_service_token="internal-secret",
        ),
    )
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"ok": True}

    def fake_get(*args, **kwargs):
        captured["headers"] = kwargs["headers"]
        return FakeResponse()

    monkeypatch.setattr(remote_client.requests, "get", fake_get)

    payload = remote_client.remote_bff_get(
        "http://remote-bff.example.invalid:18090",
        "/api/bff/v1/workspace/paper",
        forward_headers={
            "Authorization": "Bearer user-token",
            "Cookie": "refresh=secret",
            "X-Admin-Token": "admin-token",
        },
    )

    assert payload == {"ok": True}
    assert captured["headers"] == {"X-TQuant-Bff-Hop": "1"}


def test_remote_client_forwards_request_id_to_trusted_target(monkeypatch) -> None:
    remote_client._CIRCUIT_OPEN_UNTIL.clear()
    monkeypatch.setattr(
        remote_client,
        "get_settings",
        lambda: SimpleNamespace(
            tquant_service_call_timeout_seconds=1.0,
            tquant_service_circuit_breaker_seconds=30.0,
            tquant_internal_service_token="internal-secret",
        ),
    )
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"ok": True}

    def fake_get(*args, **kwargs):
        captured["headers"] = kwargs["headers"]
        return FakeResponse()

    monkeypatch.setattr(remote_client.requests, "get", fake_get)

    payload = remote_client.remote_bff_get(
        "http://trade-service",
        "/api/bff/v1/workspace/paper",
        forward_headers={
            "Authorization": "Bearer user-token",
            "X-Request-ID": "req-test-123",
        },
    )

    assert payload == {"ok": True}
    assert captured["headers"]["Authorization"] == "Bearer user-token"
    assert captured["headers"]["X-Request-ID"] == "req-test-123"
    assert captured["headers"]["X-Internal-Service-Token"] == "internal-secret"
    assert captured["headers"]["X-TQuant-Bff-Hop"] == "1"
    metrics = remote_client.remote_bff_metrics_snapshot()
    assert metrics["calls"] >= 1
    assert metrics["successes"] >= 1


def test_remote_client_opens_circuit_after_failure(monkeypatch) -> None:
    remote_client._CIRCUIT_OPEN_UNTIL.clear()
    monkeypatch.setattr(
        remote_client,
        "get_settings",
        lambda: SimpleNamespace(
            tquant_service_call_timeout_seconds=1.0,
            tquant_service_circuit_breaker_seconds=30.0,
            tquant_internal_service_token="",
        ),
    )
    calls = {"count": 0}

    def failing_get(*args, **kwargs):
        calls["count"] += 1
        raise remote_client.requests.ConnectionError("offline")

    monkeypatch.setattr(remote_client.requests, "get", failing_get)

    with pytest.raises(remote_client.RemoteBffError):
        remote_client.remote_bff_get("http://trade-service", "/api/bff/v1/workspace/paper")
    with pytest.raises(remote_client.RemoteBffError):
        remote_client.remote_bff_get("http://trade-service", "/api/bff/v1/workspace/paper")

    assert calls["count"] == 1
    metrics = remote_client.remote_bff_metrics_snapshot()
    assert metrics["failures"] >= 1
    assert metrics["circuit_short_circuits"] >= 1


def test_bff_workspace_cache_reuses_valid_payload(monkeypatch) -> None:
    calls = {"count": 0}
    cache: dict[str, object] = {}

    monkeypatch.setattr(
        workspace_cache,
        "get_settings",
        lambda: SimpleNamespace(
            bff_workspace_cache_enabled=True,
            bff_monitor_cache_ttl_seconds=5,
            bff_paper_cache_ttl_seconds=3,
            bff_strategy_cache_ttl_seconds=30,
            bff_settings_cache_ttl_seconds=30,
        ),
    )
    monkeypatch.setattr(workspace_cache, "get_json_cache", lambda key: cache.get(key))
    monkeypatch.setattr(workspace_cache, "set_json_cache", lambda key, value, ttl: cache.setdefault(key, value))

    def loader():
        calls["count"] += 1
        return PaperWorkspaceBffResponse(
            generated_at="2026-05-22 09:30:00",
            auto_trading_status={"source": "local"},
        )

    first = workspace_cache.load_cached_workspace(
        workspace="paper",
        model=PaperWorkspaceBffResponse,
        user_id=7,
        params={"order_limit": 5},
        loader=loader,
    )
    second = workspace_cache.load_cached_workspace(
        workspace="paper",
        model=PaperWorkspaceBffResponse,
        user_id=7,
        params={"order_limit": 5},
        loader=loader,
    )

    assert calls["count"] == 1
    assert first.auto_trading_status == second.auto_trading_status == {"source": "local"}
    metrics = workspace_cache.bff_workspace_cache_metrics_snapshot()
    assert metrics["reads"] >= 2
    assert metrics["hits"] >= 1
    assert metrics["writes"] >= 1
