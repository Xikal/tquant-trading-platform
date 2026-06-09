from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import instruments
from app.core.auth import get_current_user
from app.services.market import MarketDataService
from app.services.market.providers.quality import MarketDataQuality, ProviderResult


def _override_user():
    return SimpleNamespace(id=1, username="tester", is_active=True)


def _client_with_market_data(monkeypatch, market_data) -> TestClient:  # noqa: ANN001
    app = FastAPI()
    app.include_router(instruments.router, prefix="/api")
    app.dependency_overrides[get_current_user] = _override_user
    monkeypatch.setattr(instruments, "market_data", market_data)
    return TestClient(app)


def test_kline_daily_uses_daily_bars_contract(monkeypatch):
    calls: list[tuple[str, str, int]] = []

    def daily(symbol: str, limit: int):
        calls.append(("daily", symbol, limit))
        return [
            SimpleNamespace(
                model_dump=lambda: {
                    "timestamp": "2026-06-01",
                    "open": 8.0,
                    "high": 8.2,
                    "low": 7.9,
                    "close": 8.1,
                    "volume": 1000,
                    "amount": 8000,
                }
            )
        ]

    market_data = SimpleNamespace(
        get_daily_bars=daily,
        get_intraday_bars=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("daily must not call intraday")),
    )
    response = _client_with_market_data(monkeypatch, market_data).get("/api/kline/000001?period=daily&limit=120")

    assert response.status_code == 200
    body = response.json()
    assert body["period"] == "daily"
    assert body["bars"][0]["timestamp"] == "2026-06-01"
    assert calls == [("daily", "000001", 120)]


def test_kline_intraday_still_uses_intraday_bars(monkeypatch):
    calls: list[tuple[str, str, int]] = []

    def intraday(symbol: str, period: str, limit: int):
        calls.append((symbol, period, limit))
        return [
            SimpleNamespace(
                model_dump=lambda: {
                    "timestamp": "2026-06-01 09:35",
                    "open": 8.0,
                    "high": 8.1,
                    "low": 7.99,
                    "close": 8.05,
                    "volume": 100,
                    "amount": 805,
                }
            )
        ]

    market_data = SimpleNamespace(
        get_daily_bars=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("intraday must not call daily")),
        get_intraday_bars=intraday,
    )
    response = _client_with_market_data(monkeypatch, market_data).get("/api/kline/000001?period=5m&limit=80")

    assert response.status_code == 200
    body = response.json()
    assert body["period"] == "5m"
    assert body["bars"][0]["timestamp"] == "2026-06-01 09:35"
    assert calls == [("000001", "5m", 80)]


def test_market_data_daily_bars_parse_provider_history():
    calls: list[tuple[str, str, str]] = []
    service = MarketDataService()

    def fetch_daily_history(symbol: str, start_date: str, end_date: str):
        calls.append((symbol, start_date, end_date))
        return ProviderResult(
            quality=MarketDataQuality.FRESH,
            source="unit",
            data=[
                {"trade_date": "2026-05-29", "open_price": 7.9, "high_price": 8.1, "low_price": 7.8, "close_price": 8.0, "volume": 1000, "amount": 8000, "pct_chg": 1.2},
                {"trade_date": "2026-06-01", "open_price": 8.0, "high_price": 8.4, "low_price": 7.95, "close_price": 8.3, "volume": 1200, "amount": 9960, "pct_chg": 3.75},
                {"trade_date": "2026-06-02", "open_price": 8.3, "high_price": 8.5, "low_price": 8.1, "close_price": 8.2, "volume": 900, "amount": 7380, "pct_chg": -1.2},
            ],
        )

    service.provider_router = SimpleNamespace(fetch_daily_history=fetch_daily_history)

    bars = service.get_daily_bars("000001", limit=2)

    assert [bar.timestamp for bar in bars] == ["2026-06-01", "2026-06-02"]
    assert bars[0].open == 8.0
    assert bars[0].high == 8.4
    assert bars[0].low == 7.95
    assert bars[0].close == 8.3
    assert bars[0].change_pct == 3.75
    assert calls[0][0] == "000001"
