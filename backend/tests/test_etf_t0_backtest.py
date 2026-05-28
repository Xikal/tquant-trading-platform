from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import backtests as backtests_route
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.schemas import KlineBar
from app.services.etf.t0_backtest import run_etf_t0_backtest, run_etf_t0_research_report


def test_etf_t0_backtest_replays_minute_positive_t_with_costs_and_baseline() -> None:
    report = run_etf_t0_backtest(
        symbol="510300",
        name="沪深300ETF",
        bars=_bars([10.0] * 17 + [9.95, 9.90, 9.85, 9.86, 9.88, 9.92, 9.96, 10.0, 10.02]),
        quantity=10_000,
        min_signal_bars=20,
        max_trades_per_day=1,
        params={"signal_max_trend_slope_abs_pct": 5.0, "signal_min_net_edge_pct": 0.05},
    )

    assert report.version == "etf-t0-backtest-v1"
    assert report.trade_count == 1
    assert report.trades[0].side == "positive_t"
    assert report.trades[0].gross_pnl > report.trades[0].net_pnl
    assert report.trades[0].total_fee > 0
    assert report.baseline_no_trade_return_pct == 0.0
    assert report.baseline_hold_return_pct != 0.0


def test_etf_t0_backtest_replays_negative_t_sell_then_buyback() -> None:
    report = run_etf_t0_backtest(
        symbol="510300",
        name="沪深300ETF",
        bars=_bars([10.0] * 17 + [10.10, 10.20, 10.30, 10.28, 10.25, 10.20, 10.15, 10.10, 10.05, 10.0]),
        quantity=10_000,
        min_signal_bars=20,
        max_trades_per_day=1,
        params={"signal_max_trend_slope_abs_pct": 5.0, "signal_min_net_edge_pct": 0.05},
    )

    assert report.trade_count == 1
    assert report.trades[0].side == "negative_t"
    assert report.trades[0].entry_price > report.trades[0].exit_price
    assert report.trades[0].net_pnl > 0


def test_etf_t0_backtest_refuses_unknown_sector_etf() -> None:
    report = run_etf_t0_backtest(
        symbol="512999",
        name="测试行业ETF",
        bars=_bars([10.0] * 30),
        quantity=10_000,
        min_signal_bars=20,
        max_trades_per_day=1,
    )

    assert report.trade_count == 0
    assert report.net_pnl == 0.0
    assert "未放行 T+0" in report.notes[0]


def test_etf_t0_backtest_limits_daily_trade_count() -> None:
    prices = [10.0] * 17 + [9.95, 9.90, 9.85, 9.86, 9.88, 9.92, 9.96, 10.0, 10.02]
    report = run_etf_t0_backtest(
        symbol="510300",
        name="沪深300ETF",
        bars=_bars(prices + prices),
        quantity=10_000,
        min_signal_bars=20,
        max_trades_per_day=1,
        params={"signal_max_trend_slope_abs_pct": 5.0, "signal_min_net_edge_pct": 0.05},
    )

    assert report.trade_count == 1


def test_etf_t0_research_report_builds_heatmap_and_regime_validation() -> None:
    report = run_etf_t0_research_report(
        symbol="510300",
        name="沪深300ETF",
        bars=_bars(([10.0] * 17 + [9.95, 9.90, 9.85, 9.86, 9.88, 9.92, 9.96, 10.0, 10.02]) * 5),
        quantity=10_000,
        min_signal_bars=20,
        max_trades_per_day=3,
        params={"signal_max_trend_slope_abs_pct": 5.0, "signal_min_net_edge_pct": 0.05},
        vwap_deviation_values=[0.25, 0.35],
        oversold_rsi_values=[34, 38],
    )

    assert report.version == "etf-t0-research-v1"
    assert report.research_only is True
    assert report.base_report.version == "etf-t0-backtest-v1"
    assert len(report.heatmap) == 4
    assert {item.regime for item in report.regime_validations} == {"牛市", "震荡", "熊市", "退潮", "强反弹"}
    assert "不自动提升为生产参数" in report.notes[0]


def test_etf_t0_backtest_route_requires_research_role() -> None:
    client = _client_for_user(roles="")

    response = client.post("/api/backtests/etf-t0-minute", json=_route_payload())

    assert response.status_code == 403


def test_etf_t0_backtest_route_returns_typed_research_report() -> None:
    client = _client_for_user(roles="backtest_research")

    response = client.post("/api/backtests/etf-t0-minute", json=_route_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "etf-t0-backtest-v1"
    assert body["trade_count"] == 1
    assert body["trades"][0]["signal_snapshot"]["version"] == "etf-t0-signal-v1"


def test_etf_t0_research_route_returns_heatmap_and_regimes() -> None:
    client = _client_for_user(roles="backtest_research")

    response = client.post("/api/backtests/etf-t0-research", json={
        **_route_payload(),
        "vwap_deviation_values": [0.25, 0.35],
        "oversold_rsi_values": [34, 38],
    })

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "etf-t0-research-v1"
    assert body["research_only"] is True
    assert len(body["heatmap"]) == 4
    assert len(body["regime_validations"]) == 5


def _route_payload() -> dict:
    return {
        "symbol": "510300",
        "name": "沪深300ETF",
        "quantity": 10000,
        "min_signal_bars": 20,
        "max_trades_per_day": 1,
        "params": {"signal_max_trend_slope_abs_pct": 5.0, "signal_min_net_edge_pct": 0.05},
        "bars": [bar.model_dump() for bar in _bars([10.0] * 17 + [9.95, 9.90, 9.85, 9.86, 9.88, 9.92, 9.96, 10.0, 10.02])],
    }


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


def _bars(values: list[float]) -> list[KlineBar]:
    start = datetime(2026, 5, 27, 9, 30)
    result: list[KlineBar] = []
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
