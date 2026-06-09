from __future__ import annotations

from app.api.router import api_router


def test_main_api_router_exposes_no_paper_routes_after_feature_removal() -> None:
    paths = {getattr(route, "path", "") for route in api_router.routes}

    assert not [path for path in paths if "/paper" in path]
    assert "/admin/users/whitelist" not in paths
