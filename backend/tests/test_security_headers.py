from __future__ import annotations

from starlette.datastructures import Headers, URL
from starlette.responses import Response

from app.main import _apply_security_headers


class _Request:
    url = URL("https://example.test/api/healthz")
    headers = Headers({"x-forwarded-proto": "https"})


def test_security_headers_include_hsts_for_https() -> None:
    response = Response()

    _apply_security_headers(response, _Request())

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "Strict-Transport-Security" in response.headers
