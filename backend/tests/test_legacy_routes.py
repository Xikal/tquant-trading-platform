from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app, settings


def test_legacy_routes_default_to_structured_gone() -> None:
    original = settings.legacy_route_compat_enabled
    settings.legacy_route_compat_enabled = False
    try:
        client = TestClient(app)
        response = client.get("/backtests", follow_redirects=False)
    finally:
        settings.legacy_route_compat_enabled = original

    assert response.status_code == 410
    assert response.json()["code"] == "LEGACY_ROUTE_REMOVED"
    assert response.json()["target"] == "/strategy?tab=backtest"


def test_legacy_routes_can_be_temporarily_redirected() -> None:
    original = settings.legacy_route_compat_enabled
    settings.legacy_route_compat_enabled = True
    try:
        client = TestClient(app)
        response = client.get("/research", follow_redirects=False)
    finally:
        settings.legacy_route_compat_enabled = original

    assert response.status_code == 301
    assert response.headers["location"] == "/strategy?tab=replay"


def test_api_get_paths_do_not_fall_back_to_frontend_html() -> None:
    client = TestClient(app)

    response = client.get("/api/intraday/subscribe")

    assert response.status_code in {404, 405}
    assert "application/json" in response.headers["content-type"]
    assert "<!doctype html>" not in response.text.lower()
