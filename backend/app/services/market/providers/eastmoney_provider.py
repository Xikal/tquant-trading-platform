from __future__ import annotations

from app.models.schemas import KlineBar, QuoteSnapshot, SectorSnapshot
from app.services.market.providers.quality import MarketDataQuality, ProviderResult


class EastmoneyMarketProvider:
    name = "eastmoney"

    def __init__(self, service) -> None:
        self.service = service

    def fetch_quote(self, symbol: str) -> ProviderResult[QuoteSnapshot]:
        try:
            quote = self.service._fetch_eastmoney_realtime_quote(symbol)
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        quality = MarketDataQuality.STALE if getattr(quote, "is_stale", False) else MarketDataQuality.FRESH
        return ProviderResult(quality=quality, source=getattr(quote, "data_source", self.name) or self.name, data=quote)

    def fetch_intraday_bars(self, symbol: str) -> ProviderResult[list[KlineBar]]:
        try:
            bars = self.service._fetch_trend_bars(symbol)
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(
            quality=MarketDataQuality.FRESH if bars else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=bars or None,
        )

    def fetch_sector_heatmap(self) -> ProviderResult[list[SectorSnapshot]]:
        return ProviderResult(
            quality=MarketDataQuality.UNAVAILABLE,
            source=self.name,
            message="sector heatmap not provided by this adapter",
        )
