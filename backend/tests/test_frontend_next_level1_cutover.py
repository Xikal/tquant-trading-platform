from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import main


def _write_next_dist(root: Path, marker: str = "next-page", asset_name: str = "next.js") -> None:
    assets = root / "assets"
    assets.mkdir(parents=True)
    (root / "index.html").write_text(f"<html><body>{marker}</body></html>", encoding="utf-8")
    (assets / asset_name).write_text(f"console.log('{marker}')", encoding="utf-8")


def test_root_and_business_routes_use_frontend_next(monkeypatch, tmp_path):
    next_dist = tmp_path / "frontend-next" / "dist"
    _write_next_dist(next_dist, "next-only")

    monkeypatch.setattr(main, "FRONTEND_NEXT_DIST_DIR", next_dist)
    monkeypatch.setattr(main, "FRONTEND_NEXT_INDEX_FILE", next_dist / "index.html")

    with TestClient(main.app) as client:
        root_response = client.get("/")
        route_responses = {
            path: client.get(path)
            for path in (
                "/monitor",
                "/monitor/market",
                "/paper",
                "/strategy-tracking",
                "/analysis",
                "/playbook",
                "/backtest",
                "/data",
                "/settings",
                "/next/monitor",
            )
        }
        next_asset_response = client.get("/next/assets/next.js")
        root_asset_response = client.get("/assets/next.js")
        missing_next_asset_response = client.get("/next/assets/missing.js")
        missing_root_asset_response = client.get("/assets/missing.css")
        legacy_asset_response = client.get("/__legacy/assets/legacy.js")
        api_response = client.get("/api/__missing_smoke__")

    assert root_response.status_code == 200
    assert "next-only" in root_response.text
    assert root_response.headers["cache-control"] == "no-store, no-cache, must-revalidate, proxy-revalidate"
    for path, response in route_responses.items():
        assert response.status_code == 200, path
        assert "next-only" in response.text, path
        assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate, proxy-revalidate", path
    assert next_asset_response.status_code == 200
    assert "next-only" in next_asset_response.text
    assert "cache-control" not in next_asset_response.headers
    assert root_asset_response.status_code == 200
    assert "next-only" in root_asset_response.text
    assert missing_next_asset_response.status_code == 404
    assert missing_next_asset_response.json() == {"detail": "Frontend asset not found"}
    assert missing_root_asset_response.status_code == 404
    assert missing_root_asset_response.json() == {"detail": "Frontend asset not found"}
    assert legacy_asset_response.status_code == 404
    assert legacy_asset_response.json() == {"detail": "Legacy frontend assets have been retired"}
    assert api_response.status_code == 404
    assert api_response.json() == {"detail": "API endpoint not found"}


def test_readyz_requires_frontend_next_dist_and_keeps_compat_alias(monkeypatch, tmp_path):
    missing_next_dist = tmp_path / "frontend-next" / "dist"
    monkeypatch.setattr(main, "FRONTEND_NEXT_INDEX_FILE", missing_next_dist / "index.html")
    monkeypatch.setattr(main, "ping_database", lambda: True)

    class _AnalyticsStatus:
        ready = True
        enabled = False
        error = ""

    monkeypatch.setattr(main, "analytics_dependency_status", lambda: _AnalyticsStatus())

    response = main.readyz(type("ResponseStub", (), {"status_code": 200})())

    assert response.status == "degraded"
    assert response.checks["frontend_next_dist"] is False
    assert response.checks["frontend_dist"] is False
    assert response.errors == ["frontend_next_dist: missing frontend-next/dist/index.html"]

    _write_next_dist(missing_next_dist, "next-ready")
    response = main.readyz(type("ResponseStub", (), {"status_code": 200})())

    assert response.status == "ok"
    assert response.checks["frontend_next_dist"] is True
    assert response.checks["frontend_dist"] is True
    assert response.errors == []


def test_api_only_mode_disables_backend_static_fallback(monkeypatch, tmp_path):
    next_dist = tmp_path / "frontend-next" / "dist"
    _write_next_dist(next_dist, "next-page")
    monkeypatch.setattr(main, "FRONTEND_NEXT_DIST_DIR", next_dist)
    monkeypatch.setattr(main, "FRONTEND_NEXT_INDEX_FILE", next_dist / "index.html")
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
    missing_next_dist = tmp_path / "frontend-next" / "dist"

    monkeypatch.setattr(main, "FRONTEND_NEXT_INDEX_FILE", missing_next_dist / "index.html")
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
