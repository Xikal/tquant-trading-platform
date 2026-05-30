from __future__ import annotations

from app.main import app


def test_backtests_openapi_uses_v2_contract_for_root_path():
    schema = app.openapi()
    operation = schema["paths"]["/api/backtests"]["post"]
    request_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    response_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]

    assert request_ref.endswith("/BacktestRunCreate")
    assert response_ref.endswith("/BacktestRunDetail")
    assert "/api/research/backtests" not in schema["paths"]
