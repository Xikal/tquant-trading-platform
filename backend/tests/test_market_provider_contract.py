from __future__ import annotations

from pathlib import Path
import asyncio
import pandas as pd
from types import SimpleNamespace

from app.services.market.openbb_adapter import OpenBBQuote
from app.services.market import MarketDataService
from app.models.schemas import QuoteSnapshot
from app.services.market.providers.akshare_provider import AkshareMarketProvider
from app.services.market.providers.openbb_provider import OpenBBMarketProvider
from app.services.market.providers.circuit import ProviderCircuitConfig, ProviderCircuitRegistry
from app.services.market.providers.circuit_state import ProviderCircuitStore
from app.services.market.providers.quality import MarketDataQuality, ProviderResult
from app.services.market.providers.router import MarketProviderRouter
from app.services.market.sectors import MarketSectorMixin


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


def test_force_refresh_batch_bypasses_cached_provider_quote(monkeypatch) -> None:
    class Router:
        count = 0

        def fetch_quote(self, symbol):
            self.count += 1
            return ProviderResult(
                quality=MarketDataQuality.FRESH,
                source="stub",
                data=QuoteSnapshot(
                    symbol=symbol,
                    name="测试",
                    market="SH",
                    instrument_type="stock",
                    last_price=10.0 + self.count,
                    change_pct=0.0,
                    change_amount=0.0,
                    open_price=10.0,
                    high_price=10.0 + self.count,
                    low_price=10.0,
                    prev_close=10.0,
                    volume=1000,
                    amount=10000,
                    timestamp="2026-05-07 10:00:00",
                ),
            )

    MarketDataService._quote_cache.clear()
    service = MarketDataService()
    router = Router()
    service.provider_router = router
    monkeypatch.setattr(service, "_market_provider_router_enabled", lambda: True)

    first = service.get_quote("600000")
    refreshed = service.get_quotes_batch(["600000"], force_refresh=True)["600000"]

    assert first.last_price == 11.0
    assert refreshed.last_price == 12.0
    assert router.count == 2


def test_async_provider_batch_fetches_eastmoney_chunks_concurrently(monkeypatch) -> None:
    service = MarketDataService()
    service._quote_cache.clear()
    settings = service.settings.model_copy(
        update={
            "market_quote_async_provider_chunk_size": 1,
            "market_quote_async_provider_concurrency": 2,
            "market_provider_call_timeout_seconds": 1.0,
        }
    )
    service.settings = settings
    service.provider_router.circuits = ProviderCircuitRegistry(ProviderCircuitConfig(), store=ProviderCircuitStore())
    started: list[str] = []
    started_order: list[tuple[str, int]] = []
    finished_count = 0

    async def fake_get_json(_client, _url, params):  # noqa: ANN001
        nonlocal finished_count
        symbol = str(params["secids"]).split(".", 1)[-1]
        started.append(symbol)
        started_order.append((symbol, finished_count))
        while len(started_order) < 2:
            await asyncio.sleep(0)
        await asyncio.sleep(0)
        finished_count += 1
        return {
            "rc": 0,
            "data": {
                "diff": [
                    {
                        "f12": symbol,
                        "f13": "0",
                        "f14": f"测试{symbol}",
                        "f2": 10.0,
                        "f3": 1.0,
                        "f4": 0.1,
                        "f5": 1000,
                        "f6": 10000,
                        "f15": 10.2,
                        "f16": 9.8,
                        "f17": 9.9,
                        "f18": 9.9,
                        "f8": 1.1,
                        "f10": 1.2,
                        "f124": 1780000000,
                    }
                ]
            },
        }

    monkeypatch.setattr("app.services.market.quotes._async_http_get_json", fake_get_json)

    result = service.get_quotes_batch_async_provider(["000001", "000002"], force_refresh=True, allow_slow_fallback=False)

    assert set(result) == {"000001", "000002"}
    assert started == ["000001", "000002"]
    assert started_order == [("000001", 0), ("000002", 0)]
    assert finished_count == 2
    assert result["000001"].data_source == "eastmoney_realtime"


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
        def _call_akshare(self, func, *args, purpose="default", **kwargs):  # noqa: ANN001
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


def test_market_services_keep_raw_akshare_inside_provider_boundary() -> None:
    services_root = Path(__file__).resolve().parents[1] / "app" / "services"
    allowed_parts = {
        ("market", "providers"),
        ("market", "raw_sources.py"),
        ("market", "service.py"),
    }
    offenders: list[str] = []
    for path in services_root.rglob("*.py"):
        rel = path.relative_to(services_root)
        if rel.parts[:2] in allowed_parts or rel.parts in allowed_parts:
            continue
        text = path.read_text(encoding="utf-8")
        if "self.ak." in text or "_call_akshare(" in text:
            offenders.append(str(rel))

    assert offenders == []


def test_sector_snapshot_accepts_normalized_provider_board_fields() -> None:
    class _SectorService(MarketSectorMixin):
        _sector_board_cache = {}

        def _board_breadth_frame_from_provider(self):
            return pd.DataFrame([{"industry": "机器人", "change_pct": 2.0}])

    service = _SectorService()
    instrument = SimpleNamespace(
        symbol="002112",
        market="SZ",
        instrument_type="stock",
        sector_name="机器人",
    )
    bars = [SimpleNamespace(close=10.0) for _ in range(20)]

    sector = service.get_sector_snapshot(instrument, bars)

    assert sector.sector_name == "机器人"
    assert sector.sector_strength > 50
    assert "机器人" in sector.notes
