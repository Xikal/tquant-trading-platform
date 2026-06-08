from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import main


def _write_dist(root: Path, marker: str, asset_name: str) -> None:
    assets = root / "assets"
    assets.mkdir(parents=True)
    (root / "index.html").write_text(f"<html><body>{marker}</body></html>", encoding="utf-8")
    (assets / asset_name).write_text(f"console.log('{marker}')", encoding="utf-8")


def test_monitor_uses_legacy_frontend_until_level1_cutover_enabled(monkeypatch, tmp_path):
    legacy_dist = tmp_path / "frontend" / "dist"
    next_dist = tmp_path / "frontend-next" / "dist"
    _write_dist(legacy_dist, "legacy-monitor", "legacy.js")
    _write_dist(next_dist, "next-monitor", "next.js")

    monkeypatch.setattr(main, "FRONTEND_DIST_DIR", legacy_dist)
    monkeypatch.setattr(main, "FRONTEND_INDEX_FILE", legacy_dist / "index.html")
    monkeypatch.setattr(main, "FRONTEND_NEXT_DIST_DIR", next_dist)
    monkeypatch.setattr(main, "FRONTEND_NEXT_INDEX_FILE", next_dist / "index.html")
    monkeypatch.setattr(main, "frontend_next_cutover_paths", lambda: frozenset())

    with TestClient(main.app) as client:
        response = client.get("/monitor")

    assert response.status_code == 200
    assert "legacy-monitor" in response.text


def test_monitor_and_next_routes_use_frontend_next_when_level1_cutover_enabled(monkeypatch, tmp_path):
    legacy_dist = tmp_path / "frontend" / "dist"
    next_dist = tmp_path / "frontend-next" / "dist"
    _write_dist(legacy_dist, "legacy-monitor", "legacy.js")
    _write_dist(next_dist, "next-monitor", "next.js")

    monkeypatch.setattr(main, "FRONTEND_DIST_DIR", legacy_dist)
    monkeypatch.setattr(main, "FRONTEND_INDEX_FILE", legacy_dist / "index.html")
    monkeypatch.setattr(main, "FRONTEND_NEXT_DIST_DIR", next_dist)
    monkeypatch.setattr(main, "FRONTEND_NEXT_INDEX_FILE", next_dist / "index.html")
    monkeypatch.setattr(main, "frontend_next_cutover_paths", lambda: frozenset({"monitor"}))

    with TestClient(main.app) as client:
        monitor_response = client.get("/monitor")
        next_response = client.get("/next/monitor")
        next_asset_response = client.get("/next/assets/next.js")
        legacy_asset_response = client.get("/assets/legacy.js")
        api_response = client.get("/api/does-not-exist")

    assert monitor_response.status_code == 200
    assert "next-monitor" in monitor_response.text
    assert next_response.status_code == 200
    assert "next-monitor" in next_response.text
    assert next_asset_response.status_code == 200
    assert "next-monitor" in next_asset_response.text
    assert legacy_asset_response.status_code == 200
    assert "legacy-monitor" in legacy_asset_response.text
    assert api_response.status_code == 404
    assert api_response.json() == {"detail": "API endpoint not found"}


def test_readyz_requires_frontend_next_dist_only_when_level1_cutover_enabled(monkeypatch, tmp_path):
    legacy_dist = tmp_path / "frontend" / "dist"
    next_dist = tmp_path / "frontend-next" / "dist"
    _write_dist(legacy_dist, "legacy-monitor", "legacy.js")

    monkeypatch.setattr(main, "FRONTEND_INDEX_FILE", legacy_dist / "index.html")
    monkeypatch.setattr(main, "FRONTEND_NEXT_INDEX_FILE", next_dist / "index.html")
    monkeypatch.setattr(main, "ping_database", lambda: True)

    class _AnalyticsStatus:
        ready = True
        enabled = False
        error = ""

    monkeypatch.setattr(main, "analytics_dependency_status", lambda: _AnalyticsStatus())
    monkeypatch.setattr(main, "frontend_next_cutover_paths", lambda: frozenset())
    response = main.readyz(type("ResponseStub", (), {"status_code": 200})())
    assert response.status == "ok"

    monkeypatch.setattr(main, "frontend_next_cutover_paths", lambda: frozenset({"monitor"}))
    response = main.readyz(type("ResponseStub", (), {"status_code": 200})())
    assert response.status == "degraded"
    assert "frontend_next_dist" in response.checks


def test_level2_allowlisted_legacy_routes_use_frontend_next(monkeypatch, tmp_path):
    legacy_dist = tmp_path / "frontend" / "dist"
    next_dist = tmp_path / "frontend-next" / "dist"
    _write_dist(legacy_dist, "legacy-page", "legacy.js")
    _write_dist(next_dist, "next-page", "next.js")

    monkeypatch.setattr(main, "FRONTEND_DIST_DIR", legacy_dist)
    monkeypatch.setattr(main, "FRONTEND_INDEX_FILE", legacy_dist / "index.html")
    monkeypatch.setattr(main, "FRONTEND_NEXT_DIST_DIR", next_dist)
    monkeypatch.setattr(main, "FRONTEND_NEXT_INDEX_FILE", next_dist / "index.html")
    monkeypatch.setattr(main, "frontend_next_cutover_paths", lambda: frozenset({"monitor", "paper"}))

    with TestClient(main.app) as client:
        paper_response = client.get("/paper")
        analysis_response = client.get("/analysis")

    assert paper_response.status_code == 200
    assert "next-page" in paper_response.text
    assert analysis_response.status_code == 200
    assert "legacy-page" in analysis_response.text


def test_cutover_all_serves_root_and_supported_legacy_routes_from_frontend_next(monkeypatch, tmp_path):
    legacy_dist = tmp_path / "frontend" / "dist"
    next_dist = tmp_path / "frontend-next" / "dist"
    _write_dist(legacy_dist, "legacy-all", "legacy.js")
    _write_dist(next_dist, "next-all", "next.js")

    monkeypatch.setattr(main, "FRONTEND_DIST_DIR", legacy_dist)
    monkeypatch.setattr(main, "FRONTEND_INDEX_FILE", legacy_dist / "index.html")
    monkeypatch.setattr(main, "FRONTEND_NEXT_DIST_DIR", next_dist)
    monkeypatch.setattr(main, "FRONTEND_NEXT_INDEX_FILE", next_dist / "index.html")
    monkeypatch.setattr(
        main,
        "frontend_next_cutover_paths",
        lambda: frozenset({"", "monitor", "paper", "strategy-tracking", "analysis", "playbook", "backtest", "data", "settings"}),
    )

    with TestClient(main.app) as client:
        root_response = client.get("/")
        route_responses = {
            path: client.get(path)
            for path in (
                "/monitor",
                "/paper",
                "/strategy-tracking",
                "/analysis",
                "/playbook",
                "/backtest",
                "/data",
                "/settings",
            )
        }
        next_asset_response = client.get("/next/assets/next.js")
        legacy_asset_response = client.get("/assets/legacy.js")
        api_response = client.get("/api/__missing_smoke__")

    assert root_response.status_code == 200
    assert "next-all" in root_response.text
    for path, response in route_responses.items():
        assert response.status_code == 200, path
        assert "next-all" in response.text, path
    assert next_asset_response.status_code == 200
    assert "next-all" in next_asset_response.text
    assert legacy_asset_response.status_code == 200
    assert "legacy-all" in legacy_asset_response.text
    assert api_response.status_code == 404
    assert api_response.json() == {"detail": "API endpoint not found"}


def test_api_only_mode_disables_backend_static_fallback(monkeypatch, tmp_path):
    legacy_dist = tmp_path / "frontend" / "dist"
    _write_dist(legacy_dist, "legacy-page", "legacy.js")
    monkeypatch.setattr(main, "FRONTEND_DIST_DIR", legacy_dist)
    monkeypatch.setattr(main, "FRONTEND_INDEX_FILE", legacy_dist / "index.html")
    monkeypatch.setattr(main.settings, "serve_frontend_static", False)

    try:
        with TestClient(main.app) as client:
            root_response = client.get("/")
            page_response = client.get("/monitor")
            api_response = client.get("/api/does-not-exist")
    finally:
        monkeypatch.setattr(main.settings, "serve_frontend_static", True)

    assert root_response.status_code == 200
    assert root_response.json()["status"] == "ok"
    assert page_response.status_code == 404
    assert page_response.json() == {"detail": "Frontend static serving is disabled"}
    assert "<html" not in page_response.text.lower()
    assert api_response.status_code == 404
    assert api_response.json() == {"detail": "API endpoint not found"}


def test_api_only_readyz_does_not_require_static_frontend_dist(monkeypatch, tmp_path):
    missing_legacy_dist = tmp_path / "frontend" / "dist"
    missing_next_dist = tmp_path / "frontend-next" / "dist"

    monkeypatch.setattr(main, "FRONTEND_INDEX_FILE", missing_legacy_dist / "index.html")
    monkeypatch.setattr(main, "FRONTEND_NEXT_INDEX_FILE", missing_next_dist / "index.html")
    monkeypatch.setattr(main, "frontend_next_cutover_paths", lambda: frozenset({"monitor"}))
    monkeypatch.setattr(main, "ping_database", lambda: True)
    monkeypatch.setattr(main.settings, "serve_frontend_static", False)

    class _AnalyticsStatus:
        ready = True
        enabled = False
        error = ""

    monkeypatch.setattr(main, "analytics_dependency_status", lambda: _AnalyticsStatus())

    try:
        response = main.readyz(type("ResponseStub", (), {"status_code": 200})())
    finally:
        monkeypatch.setattr(main.settings, "serve_frontend_static", True)

    assert response.status == "ok"
    assert response.checks["frontend_dist"] is True
    assert response.checks["frontend_next_dist"] is True
    assert response.errors == []
