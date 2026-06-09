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
from app.models.schema_defs.bff import (
    BFF_SCHEMA_VERSION,
    MonitorWorkspaceBffResponse,
    SettingsWorkspaceBffResponse,
    StrategyWorkspaceBffResponse,
)
from app.models.schema_defs.market import MarketBreadthResponse, SectorRelativeStrengthResponse
from app.models.schema_defs.market import IntradayMarketPulse
from app.services.bff import remote_adapters, remote_client
from app.services.bff import workspace_cache
from app.services.performance.read_model_metrics import reset_read_model_metrics


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
    assert payload["schema_version"] == BFF_SCHEMA_VERSION
    assert "market" in payload["modules"]
    assert "strategy" in payload["modules"]
    assert "settings" in payload["modules"]
    assert payload["workspaces"]["strategy"]["schema_version"] == BFF_SCHEMA_VERSION
    assert "paper" not in payload["workspaces"]


def test_paper_workspace_route_is_removed() -> None:
    app = FastAPI()
    app.include_router(bff.router, prefix="/api")
    user = SimpleNamespace(id=1, username="tester", is_active=True, roles="")
    app.dependency_overrides[get_current_user] = lambda: user

    response = TestClient(app).get("/api/bff/v1/workspace/paper")

    assert response.status_code == 404


def test_strategy_workspace_timeout_returns_partial_payload(monkeypatch) -> None:
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

    def slow_builder(*args, **kwargs):
        time.sleep(0.05)
        return StrategyWorkspaceBffResponse(generated_at="2026-05-20 09:30:00")

    monkeypatch.setattr(bff, "build_strategy_workspace", slow_builder)

    response = TestClient(app).get("/api/bff/v1/workspace/strategy")

    assert response.status_code == 200
    payload = response.json()
    error = payload["partial_errors"][0]
    assert error["source"] == "strategy_workspace"
    assert error["reason"] == "timeout"
    assert error["timeout_ms"] == 10
    assert error["status_code"] is None
    assert error["fallback_source"] == "python_local"


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
            bff_strategy_cache_ttl_seconds=0,
            bff_settings_cache_ttl_seconds=0,
        ),
    )

    monkeypatch.setattr(bff, "build_monitor_snapshot", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")))
    monkeypatch.setattr(bff, "market_breadth", lambda *args, **kwargs: MarketBreadthResponse(updated_at="2026-05-25 10:00:00"))
    monkeypatch.setattr(bff, "sector_relative_strength", lambda *args: SectorRelativeStrengthResponse(updated_at="2026-05-25 10:00:00"))
    monkeypatch.setattr(
        bff,
        "latest_pulse_or_placeholder",
        lambda *_args, **_kwargs: (
            IntradayMarketPulse(
                updated_at="2026-05-25 10:00:00",
                data_quality="fresh",
                pulse_level="repair",
                pulse_text="读取物化 pulse。",
            ),
            False,
        ),
    )
    monkeypatch.setattr(bff, "build_market_review_summary", lambda *args, **kwargs: (None, []))
    monkeypatch.setattr(bff, "paired_hedge_research", lambda *args: {"updated_at": "2026-05-25 10:00:00", "ideas": []})

    response = TestClient(app).get("/api/bff/v1/workspace/monitor")

    assert response.status_code == 200
    payload = response.json()
    assert payload["monitor_snapshot"] is None
    assert payload["market_breadth"] is None
    assert payload["market_pulse"]["pulse_text"] == "读取物化 pulse。"
    error = payload["partial_errors"][0]
    assert error["source"] == "monitor_snapshot"
    assert error["reason"] == "other"
    assert error["status_code"] is None
    assert error["fallback_source"] == "python_local"


def test_bff_partial_errors_are_exposed_by_source_and_reason_metrics(monkeypatch) -> None:
    reset_read_model_metrics()
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
            bff_strategy_cache_ttl_seconds=0,
            bff_settings_cache_ttl_seconds=0,
        ),
    )
    monkeypatch.setattr(bff, "build_monitor_snapshot", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")))
    monkeypatch.setattr(bff, "market_breadth", lambda *args, **kwargs: MarketBreadthResponse(updated_at="2026-05-25 10:00:00"))
    monkeypatch.setattr(bff, "sector_relative_strength", lambda *args: SectorRelativeStrengthResponse(updated_at="2026-05-25 10:00:00"))
    monkeypatch.setattr(
        bff,
        "latest_pulse_or_placeholder",
        lambda *_args, **_kwargs: (
            IntradayMarketPulse(
                updated_at="2026-05-25 10:00:00",
                data_quality="fresh",
                pulse_level="repair",
                pulse_text="读取物化 pulse。",
            ),
            False,
        ),
    )
    monkeypatch.setattr(bff, "build_market_review_summary", lambda *args, **kwargs: (None, []))
    monkeypatch.setattr(bff, "paired_hedge_research", lambda *args: {"updated_at": "2026-05-25 10:00:00", "ideas": []})

    response = TestClient(app).get("/api/bff/v1/workspace/monitor")

    assert response.status_code == 200
    from app.services.performance.prometheus import performance_prometheus_lines

    body = "\n".join(performance_prometheus_lines())
    assert 'tquant_bff_partial_source_failures_total{source="monitor_snapshot",reason="other"} 1' in body


def test_monitor_workspace_request_path_uses_cached_snapshot_when_sources_unreachable(monkeypatch) -> None:
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
            bff_workspace_cache_enabled=True,
            bff_monitor_cache_ttl_seconds=30,
            bff_strategy_cache_ttl_seconds=0,
            bff_settings_cache_ttl_seconds=0,
        ),
    )

    def forbidden_source(*_args, **_kwargs):
        raise AssertionError("monitor workspace request path must use cached/materialized data")

    monkeypatch.setattr(bff, "load_remote_monitor_workspace", lambda *args, **kwargs: None)
    monkeypatch.setattr(bff, "build_monitor_snapshot", lambda *args, **kwargs: {"updated_at": "2026-05-25 10:00:00"})
    monkeypatch.setattr(bff, "market_breadth", forbidden_source)
    monkeypatch.setattr(bff, "sector_relative_strength", forbidden_source)
    monkeypatch.setattr(
        bff,
        "latest_pulse_or_placeholder",
        lambda *_args, **_kwargs: (
            IntradayMarketPulse(
                updated_at="2026-05-25 10:00:00",
                data_quality="fresh",
                pulse_level="repair",
                pulse_text="读取物化 pulse。",
                suggested_action="只读观察。",
                partial_errors=[],
            ),
            False,
        ),
        raising=False,
    )
    monkeypatch.setattr(bff, "build_market_review_summary", lambda *args, **kwargs: (None, []))
    monkeypatch.setattr(bff, "paired_hedge_research", forbidden_source)

    response = TestClient(app).get("/api/bff/v1/workspace/monitor")

    assert response.status_code == 200
    payload = response.json()
    assert payload["market_pulse"]["pulse_text"] == "读取物化 pulse。"
    assert payload["partial_errors"] == []


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
    monkeypatch.setattr(
        bff,
        "latest_pulse_or_placeholder",
        lambda *_args, **_kwargs: (
            IntradayMarketPulse(
                updated_at="2026-05-25 10:00:00",
                data_quality="fresh",
                pulse_level="repair",
                pulse_text="读取物化 pulse。",
            ),
            False,
        ),
    )
    monkeypatch.setattr(bff, "build_market_review_summary", lambda *args, **kwargs: (None, []))
    monkeypatch.setattr(bff, "paired_hedge_research", lambda *args: {"updated_at": "2026-05-25 10:00:00", "ideas": []})

    response = TestClient(app).get("/api/bff/v1/workspace/monitor")

    assert response.status_code == 200
    payload = response.json()
    assert payload["monitor_snapshot"]["updated_at"] == "2026-05-25 10:00:00"
    assert payload["market_breadth"] is None
    assert payload["market_pulse"]["pulse_text"] == "读取物化 pulse。"
    assert payload["partial_errors"] == []
    assert calls == {}


def test_monitor_workspace_view_action_projects_action_payload(monkeypatch) -> None:
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
            bff_strategy_cache_ttl_seconds=0,
            bff_settings_cache_ttl_seconds=0,
        ),
    )
    monkeypatch.setattr(
        bff,
        "build_monitor_snapshot",
        lambda *args, **kwargs: {
            "updated_at": "2026-06-05 10:00:00",
            "watchlist_signals": [{"symbol": "600000"}],
            "priority_board": {"items": [{"symbol": "600000", "priority_score": 80}]},
        },
    )
    monkeypatch.setattr(
        bff,
        "latest_pulse_or_placeholder",
        lambda *_args, **_kwargs: (
            IntradayMarketPulse(
                updated_at="2026-06-05 10:00:00",
                data_quality="fresh",
                pulse_level="strong",
                pulse_text="行动台总闸",
            ),
            False,
        ),
    )
    monkeypatch.setattr(bff, "build_market_review_summary", lambda *args, **kwargs: (None, []))

    response = TestClient(app).get("/api/bff/v1/workspace/monitor?view=action")

    assert response.status_code == 200
    payload = response.json()
    assert payload["monitor_snapshot"]["priority_board"]["items"][0]["symbol"] == "600000"
    assert payload["monitor_snapshot"]["watchlist_signals"][0]["symbol"] == "600000"
    assert payload["market_pulse"]["pulse_text"] == "行动台总闸"
    assert payload["market_breadth"] is None
    assert payload["review_status"] is None
    assert payload["review_reports"] == []
    assert payload["sector_relative_strength"] is None
    assert payload["paired_hedge"] is None
    assert payload["runtime"] is None


def test_remote_monitor_adapter_rejects_degraded_go_gateway_payload(monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(
        remote_adapters,
        "get_settings",
        lambda: SimpleNamespace(
            tquant_bff_gateway_url="http://go-bff-gateway",
            tquant_market_service_url="",
        ),
    )
    monkeypatch.setattr(remote_adapters, "open_remote_bff_circuit", lambda base_url: opened.append(base_url))
    monkeypatch.setattr(
        remote_adapters,
        "remote_bff_get",
        lambda *args, **kwargs: {
            "generated_at": "2026-06-09 09:45:00",
            "monitor_snapshot": None,
            "market_pulse": None,
            "partial_errors": [
                {
                    "source": "monitor_snapshot",
                    "detail": "数据暂时不可用",
                    "message": "source unavailable",
                    "fallback_source": "go_bff_gateway",
                },
                {
                    "source": "market_pulse",
                    "detail": "数据暂时不可用",
                    "message": "source unavailable",
                    "fallback_source": "go_bff_gateway",
                },
            ],
        },
    )

    result = remote_adapters.load_remote_monitor_workspace(
        priority_limit=18,
        sector_limit=8,
        per_sector_limit=8,
        hedge_limit=4,
        view="action",
    )

    assert result is None
    assert opened == ["http://go-bff-gateway"]


def test_monitor_workspace_falls_back_when_remote_monitor_adapter_returns_none(monkeypatch) -> None:
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
            bff_strategy_cache_ttl_seconds=0,
            bff_settings_cache_ttl_seconds=0,
        ),
    )
    monkeypatch.setattr(
        bff,
        "load_remote_monitor_workspace",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        bff,
        "build_monitor_snapshot",
        lambda *args, **kwargs: {
            "updated_at": "2026-06-09 09:46:00",
            "watchlist_signals": [],
            "priority_board": {
                "latest_trade_date": "2026-06-08",
                "total_candidates": 1,
                "items": [{"symbol": "600000", "name": "浦发银行", "buy_signal_text": "今日放弃"}],
            },
        },
    )
    monkeypatch.setattr(
        bff,
        "latest_pulse_or_placeholder",
        lambda *_args, **_kwargs: (
            IntradayMarketPulse(
                updated_at="2026-06-09 09:46:00",
                data_quality="fresh",
                pulse_level="repair",
                pulse_text="市场状态来自本地缓存。",
            ),
            False,
        ),
    )
    monkeypatch.setattr(bff, "build_market_review_summary", lambda *args, **kwargs: (None, []))

    response = TestClient(app).get("/api/bff/v1/workspace/monitor?view=action")

    assert response.status_code == 200
    payload = response.json()
    board = payload["monitor_snapshot"]["priority_board"]
    assert board["items"][0]["symbol"] == "600000"
    assert payload["market_pulse"]["pulse_text"] == "市场状态来自本地缓存。"
    assert payload["partial_errors"] == []


def test_monitor_workspace_view_action_skips_market_context_sources(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(bff.router, prefix="/api")
    user = SimpleNamespace(id=1, username="admin", is_active=True, roles="admin")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: object()
    monkeypatch.setattr(bff, "get_settings", lambda: SimpleNamespace(tquant_internal_service_token=""))
    monkeypatch.setattr(
        workspace_cache,
        "get_settings",
        lambda: SimpleNamespace(
            bff_workspace_cache_enabled=False,
            bff_monitor_cache_ttl_seconds=0,
            bff_strategy_cache_ttl_seconds=0,
            bff_settings_cache_ttl_seconds=0,
        ),
    )
    monkeypatch.setattr(
        bff,
        "build_monitor_snapshot",
        lambda *args, **kwargs: {
            "updated_at": "2026-06-05 10:00:00",
            "watchlist_signals": [],
            "priority_board": {"items": []},
        },
    )
    monkeypatch.setattr(
        bff,
        "latest_pulse_or_placeholder",
        lambda *_args, **_kwargs: (
            IntradayMarketPulse(
                updated_at="2026-06-05 10:00:00",
                data_quality="fresh",
                pulse_level="strong",
                pulse_text="行动台总闸",
            ),
            False,
        ),
    )
    monkeypatch.setattr(
        bff,
        "build_market_review_summary",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("action view should not build review")),
    )
    monkeypatch.setattr(
        bff,
        "list_hourly_snapshot_history",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("action view should not build hourly history")),
    )
    monkeypatch.setattr(
        bff.SettingsRuntimeDiagnosticsService,
        "build_status",
        lambda self: (_ for _ in ()).throw(AssertionError("action view should not build runtime")),
    )

    response = TestClient(app).get("/api/bff/v1/workspace/monitor?view=action")

    assert response.status_code == 200
    payload = response.json()
    assert payload["market_pulse"]["pulse_text"] == "行动台总闸"
    assert payload["review_reports"] == []
    assert payload["hourly_snapshot_history"] == []
    assert payload["runtime"] is None


def test_monitor_workspace_view_market_keeps_priority_alias_without_watchlist(monkeypatch) -> None:
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
            bff_strategy_cache_ttl_seconds=0,
            bff_settings_cache_ttl_seconds=0,
        ),
    )
    monkeypatch.setattr(
        bff,
        "build_monitor_snapshot",
        lambda *args, **kwargs: {
            "updated_at": "2026-06-05 10:00:00",
            "watchlist_signals": [{"symbol": "600000"}],
            "priority_board": {"items": [{"symbol": "600000", "priority_score": 80}]},
        },
    )
    monkeypatch.setattr(
        bff,
        "latest_pulse_or_placeholder",
        lambda *_args, **_kwargs: (
            IntradayMarketPulse(
                updated_at="2026-06-05 10:00:00",
                data_quality="fresh",
                pulse_level="repair",
                pulse_text="市场可观察",
            ),
            False,
        ),
    )
    monkeypatch.setattr(bff, "build_market_review_summary", lambda *args, **kwargs: (None, []))

    response = TestClient(app).get("/api/bff/v1/workspace/monitor?view=market")

    assert response.status_code == 200
    payload = response.json()
    assert payload["monitor_snapshot"]["priority_board"]["items"][0]["symbol"] == "600000"
    assert payload["monitor_snapshot"]["watchlist_signals"] == []
    assert payload["market_pulse"]["pulse_text"] == "市场可观察"


def test_bff_hop_header_forces_strategy_local_fallback(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(bff.router, prefix="/api")
    user = SimpleNamespace(id=1, username="tester", is_active=True, roles="")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: object()

    def forbidden_remote(*args, **kwargs):
        raise AssertionError("remote adapter should not run on a BFF hop request")

    def fake_builder(*args, **kwargs):
        return StrategyWorkspaceBffResponse(
            generated_at="2026-05-20 09:32:00",
            tracking_notes=["local"],
        )

    monkeypatch.setattr(bff, "load_remote_strategy_workspace", forbidden_remote)
    monkeypatch.setattr(bff, "build_strategy_workspace", fake_builder)
    monkeypatch.setattr(bff, "get_settings", lambda: SimpleNamespace(tquant_internal_service_token="internal-secret"))

    response = TestClient(app).get(
        "/api/bff/v1/workspace/strategy",
        headers={"X-TQuant-Bff-Hop": "1", "X-Internal-Service-Token": "internal-secret"},
    )

    assert response.status_code == 200
    assert response.json()["tracking_notes"] == ["local"]


def test_forged_bff_hop_header_does_not_skip_strategy_remote(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(bff.router, prefix="/api")
    user = SimpleNamespace(id=1, username="tester", is_active=True, roles="")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: object()

    monkeypatch.setattr(bff, "get_settings", lambda: SimpleNamespace(tquant_internal_service_token="internal-secret"))
    monkeypatch.setattr(
        bff,
        "load_remote_strategy_workspace",
        lambda *args, **kwargs: StrategyWorkspaceBffResponse(
            generated_at="2026-05-20 09:33:00",
            tracking_notes=["remote"],
        ),
    )

    response = TestClient(app).get("/api/bff/v1/workspace/strategy", headers={"X-TQuant-Bff-Hop": "1"})

    assert response.status_code == 200
    assert response.json()["tracking_notes"] == ["remote"]


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
        lambda: SimpleNamespace(tquant_strategy_service_url="http://strategy-service"),
    )
    monkeypatch.setattr(remote_adapters, "remote_bff_get", lambda *args, **kwargs: {"api_version": "v1", "schema_version": "v99"})
    opened: list[str] = []
    monkeypatch.setattr(remote_adapters, "open_remote_bff_circuit", lambda base_url: opened.append(base_url))

    with caplog.at_level(logging.WARNING):
        result = remote_adapters.load_remote_strategy_workspace(run_limit=1)

    assert result is None
    assert opened == ["http://strategy-service"]
    assert "schema_version=v99" in caplog.text
    assert "missing_fields" in caplog.text


def test_remote_adapter_remote_failure_falls_back(monkeypatch) -> None:
    monkeypatch.setattr(
        remote_adapters,
        "get_settings",
        lambda: SimpleNamespace(tquant_strategy_service_url="http://strategy-service"),
    )

    def fake_remote(*args, **kwargs):  # noqa: ANN002, ANN003
        raise remote_client.RemoteBffError("timeout")

    monkeypatch.setattr(remote_adapters, "remote_bff_get", fake_remote)

    assert remote_adapters.load_remote_strategy_workspace(run_limit=1) is None


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
        "/api/bff/v1/workspace/strategy",
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
        "/api/bff/v1/workspace/strategy",
        forward_headers={
            "Authorization": "Bearer user-token",
            "X-Request-ID": "req-test-123",
            "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        },
    )

    assert payload == {"ok": True}
    assert captured["headers"]["Authorization"] == "Bearer user-token"
    assert captured["headers"]["X-Request-ID"] == "req-test-123"
    assert captured["headers"]["traceparent"] == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
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
        remote_client.remote_bff_get("http://trade-service", "/api/bff/v1/workspace/strategy")
    with pytest.raises(remote_client.RemoteBffError):
        remote_client.remote_bff_get("http://trade-service", "/api/bff/v1/workspace/strategy")

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
            bff_strategy_cache_ttl_seconds=30,
            bff_settings_cache_ttl_seconds=30,
        ),
    )
    monkeypatch.setattr(workspace_cache, "get_json_cache", lambda key: cache.get(key))
    monkeypatch.setattr(workspace_cache, "set_json_cache", lambda key, value, ttl: cache.setdefault(key, value))

    def loader():
        calls["count"] += 1
        return StrategyWorkspaceBffResponse(
            generated_at="2026-05-22 09:30:00",
            tracking_notes=["local"],
        )

    first = workspace_cache.load_cached_workspace(
        workspace="strategy",
        model=StrategyWorkspaceBffResponse,
        user_id=7,
        params={"run_limit": 5},
        loader=loader,
    )
    second = workspace_cache.load_cached_workspace(
        workspace="strategy",
        model=StrategyWorkspaceBffResponse,
        user_id=7,
        params={"run_limit": 5},
        loader=loader,
    )

    assert calls["count"] == 1
    assert first.tracking_notes == second.tracking_notes == ["local"]
    metrics = workspace_cache.bff_workspace_cache_metrics_snapshot()
    assert metrics["reads"] >= 2
    assert metrics["hits"] >= 1
    assert metrics["writes"] >= 1
