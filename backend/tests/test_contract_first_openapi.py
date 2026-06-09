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


def test_kline_openapi_supports_daily_and_intraday_periods():
    schema = app.openapi()
    operation = schema["paths"]["/api/kline/{symbol}"]["get"]
    period_param = next(item for item in operation["parameters"] if item["name"] == "period")

    assert period_param["schema"]["pattern"] == "^(daily|1m|5m|15m)$"
    assert period_param["schema"]["default"] == "daily"
