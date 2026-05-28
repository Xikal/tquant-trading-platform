from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import backtests as backtests_route
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.schemas import KlineBar
from app.services.etf.oos_validation import run_oos_validation


def test_oos_validation_uses_manifest_segments_not_auto_split(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TQUANT_ETF_T0_OOS_RUN_LOG", str(tmp_path / "runs.jsonl"))
    result = run_oos_validation(
        dataset_key="etf_t0_oos_2026q2_v1",
        symbol="510300",
        name="沪深300ETF",
        bars=_oos_bars(),
        quantity=10_000,
        min_signal_bars=20,
        max_trades_per_day=2,
        params={"signal_max_trend_slope_abs_pct": 5.0, "signal_min_net_edge_pct": 0.05},
        vwap_deviation_values=[0.25, 0.35],
        oversold_rsi_values=[34, 38],
    )

    assert result["dataset"]["dataset_key"] == "etf_t0_oos_2026q2_v1"
    regimes = {item["regime"] for item in result["research_report"]["regime_validations"]}
    assert regimes == {"牛市", "震荡", "熊市", "退潮", "强反弹"}
    assert "自动等分" in result["notes"][0]
    assert result["stage"] in {"research_only", "paper_small", "candidate_production"}
    assert (tmp_path / "runs.jsonl").exists()


def test_oos_validation_route_requires_research_role() -> None:
    client = _client_for_user(roles="")

    response = client.post("/api/backtests/etf-t0-oos/validate", json=_route_payload())

    assert response.status_code == 403


def test_oos_validation_route_returns_dataset_quality_and_latest(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TQUANT_ETF_T0_OOS_RUN_LOG", str(tmp_path / "runs.jsonl"))
    client = _client_for_user(roles="backtest_research")

    response = client.post("/api/backtests/etf-t0-oos/validate", json=_route_payload())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["dataset"]["quality_ok"] is True
    assert body["dataset"]["covered_regimes"] == ["bear", "bull", "range", "risk_off", "strong_rebound"]
    assert body["research_report"]["research_only"] is True
    latest = client.get("/api/backtests/etf-t0-oos/latest")
    assert latest.status_code == 200
    assert latest.json()["available"] is True
    assert latest.json()["dataset_key"] == "etf_t0_oos_2026q2_v1"


def test_oos_promote_check_is_read_only(tmp_path, monkeypatch) -> None:
    run_log = tmp_path / "runs.jsonl"
    monkeypatch.setenv("TQUANT_ETF_T0_OOS_RUN_LOG", str(run_log))
    client = _client_for_user(roles="backtest_research")

    response = client.post("/api/backtests/etf-t0-oos/promote-check", json=_route_payload())

    assert response.status_code == 200
    assert response.json()["notes"] == ["promote-check 为只读检查，不修改生产状态。"]
    assert not run_log.exists()


def _client_for_user(*, roles: str) -> TestClient:
    app = FastAPI()
    app.include_router(backtests_route.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1,
        username="tester",
        roles=roles,
        is_active=True,
    )
    return TestClient(app)


def _route_payload() -> dict:
    return {
        "dataset_key": "etf_t0_oos_2026q2_v1",
        "symbol": "510300",
        "name": "沪深300ETF",
        "quantity": 10000,
        "min_signal_bars": 20,
        "max_trades_per_day": 2,
        "params": {"signal_max_trend_slope_abs_pct": 5.0, "signal_min_net_edge_pct": 0.05},
        "vwap_deviation_values": [0.25, 0.35],
        "oversold_rsi_values": [34, 38],
        "bars": [bar.model_dump() for bar in _oos_bars()],
    }


def _oos_bars() -> list[KlineBar]:
    ranges = [
        ("2026-04-01 09:30", [10.0] * 17 + [9.95, 9.90, 9.85, 9.86, 9.88, 9.92, 9.96, 10.0, 10.02]),
        ("2026-04-09 09:30", [10.0] * 17 + [10.10, 10.20, 10.30, 10.28, 10.25, 10.20, 10.15, 10.10, 10.05, 10.0]),
        ("2026-04-19 09:30", [10.0] * 26),
        ("2026-04-28 09:30", [10.0] * 26),
        ("2026-05-09 09:30", [10.0] * 17 + [9.95, 9.90, 9.85, 9.86, 9.88, 9.92, 9.96, 10.0, 10.02]),
    ]
    result: list[KlineBar] = []
    for start_text, values in ranges:
        start = datetime.strptime(start_text, "%Y-%m-%d %H:%M")
        for index, close in enumerate(values):
            timestamp = (start + timedelta(minutes=index)).strftime("%Y-%m-%d %H:%M")
            result.append(
                KlineBar(
                    timestamp=timestamp,
                    open=close,
                    high=round(close * 1.001, 4),
                    low=round(close * 0.999, 4),
                    close=close,
                    volume=1_000_000.0,
                    amount=close * 1_000_000.0,
                )
            )
    return result
