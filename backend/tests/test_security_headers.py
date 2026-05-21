from __future__ import annotations

from app import main


def test_csp_disallows_data_images_and_fonts() -> None:
    csp = main._CONTENT_SECURITY_POLICY

    assert "img-src 'self' blob:" in csp
    assert "img-src 'self' data:" not in csp
    assert "font-src 'self';" in csp
    assert "font-src 'self' data:" not in csp
    assert "fastapi.tiangolo.com" not in csp
