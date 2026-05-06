from __future__ import annotations

import pandas as pd

from app.services.market.openbb_adapter import OpenBBQuote
from app.services.market.providers.akshare_provider import AkshareMarketProvider
from app.services.market.providers.openbb_provider import OpenBBMarketProvider
from app.services.market.providers.quality import MarketDataQuality, ProviderResult
from app.services.market.providers.router import MarketProviderRouter


def test_provider_result_quality_values_are_explicit() -> None:
    assert {item.value for item in MarketDataQuality} == {
        "fresh",
        "stale",
        "estimated",
        "unavailable",
    }
    assert ProviderResult(quality=MarketDataQuality.FRESH, source="test", data={"ok": True}).usable is True
    assert ProviderResult(quality=MarketDataQuality.STALE, source="test", data={"ok": True}).usable is True
    assert ProviderResult(quality=MarketDataQuality.ESTIMATED, source="test", data={"ok": True}).usable is True
    assert ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source="test").usable is False


def test_market_provider_router_returns_first_usable_result() -> None:
    class FailedProvider:
        name = "failed"

        def fetch_quote(self, symbol):
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message="failed")

    class FreshProvider:
        name = "fresh"

        def fetch_quote(self, symbol):
            return ProviderResult(quality=MarketDataQuality.FRESH, source=self.name, data={"symbol": symbol})

    result = MarketProviderRouter([FailedProvider(), FreshProvider()]).fetch_quote("000001")

    assert result.quality == MarketDataQuality.FRESH
    assert result.source == "fresh"
    assert result.data == {"symbol": "000001"}


def test_openbb_provider_keeps_estimated_quote_fields_consistent() -> None:
    class _Settings:
        http_timeout = 1

    class _Service:
        settings = _Settings()

    class _Adapter:
        def quote(self, symbol):
            return OpenBBQuote(
                symbol=symbol,
                last_price=11.0,
                previous_close=10.0,
                change_amount=1.0,
                change_pct=10.0,
                available=True,
            )

    provider = OpenBBMarketProvider(_Service())
    provider.adapter = _Adapter()

    result = provider.fetch_quote("TEST")

    assert result.quality == MarketDataQuality.ESTIMATED
    assert result.data is not None
    assert result.data.prev_close == 10.0
    assert result.data.change_amount == 1.0
    assert result.data.change_pct == 10.0


def test_akshare_sector_provider_uses_raw_board_frame_without_service_recursion() -> None:
    class _Service:
        def _load_board_breadth_frame(self):
            return pd.DataFrame(
                [
                    {"industry": "半导体", "change_pct": 2.0},
                    {"industry": "机器人", "change_pct": 1.0},
                ]
            )

        def get_sector_heatmap(self):
            raise AssertionError("provider must not call service.get_sector_heatmap")

    result = AkshareMarketProvider(_Service()).fetch_sector_heatmap()

    assert result.quality == MarketDataQuality.FRESH
    assert result.data is not None
    assert [item.sector_name for item in result.data] == ["半导体", "机器人"]
