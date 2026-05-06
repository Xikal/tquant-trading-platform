from __future__ import annotations

from typing import Protocol, TypeVar

from app.services.market.providers.quality import MarketDataQuality, ProviderResult


T = TypeVar("T")


class MarketProvider(Protocol):
    name: str

    def fetch_quote(self, symbol: str): ...

    def fetch_intraday_bars(self, symbol: str): ...

    def fetch_sector_heatmap(self): ...


class MarketProviderRouter:
    def __init__(self, providers: list[MarketProvider]) -> None:
        self.providers = providers

    def fetch_quote(self, symbol: str) -> ProviderResult:
        return self._first_usable(lambda provider: provider.fetch_quote(symbol))

    def fetch_intraday_bars(self, symbol: str) -> ProviderResult:
        return self._first_usable(lambda provider: provider.fetch_intraday_bars(symbol))

    def fetch_sector_heatmap(self) -> ProviderResult:
        return self._first_usable(lambda provider: provider.fetch_sector_heatmap())

    def _first_usable(self, call) -> ProviderResult:
        last_result: ProviderResult | None = None
        for provider in self.providers:
            result = call(provider)
            last_result = result
            if result.usable:
                return result
        return last_result or ProviderResult(
            quality=MarketDataQuality.UNAVAILABLE,
            source="none",
            message="no provider configured",
        )
