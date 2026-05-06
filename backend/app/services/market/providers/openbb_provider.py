from __future__ import annotations

from app.models.schemas import KlineBar, QuoteSnapshot, SectorSnapshot
from app.services.market.openbb_adapter import OpenBBDataAdapter
from app.services.market.providers.quality import MarketDataQuality, ProviderResult
from app.services.market.shared import guess_instrument_type, guess_market


class OpenBBMarketProvider:
    name = "openbb"

    def __init__(self, service) -> None:
        self.service = service
        self.adapter = OpenBBDataAdapter(timeout=getattr(service.settings, "http_timeout", 3))

    def fetch_quote(self, symbol: str) -> ProviderResult[QuoteSnapshot]:
        quote = self.adapter.quote(symbol)
        if not quote.available or quote.last_price <= 0:
            return ProviderResult(
                quality=MarketDataQuality.UNAVAILABLE,
                source=self.name,
                message=quote.message[:160],
            )
        snapshot = QuoteSnapshot(
            symbol=quote.symbol,
            name=quote.symbol,
            market=guess_market(quote.symbol),
            instrument_type=guess_instrument_type(quote.symbol),
            last_price=quote.last_price,
            change_pct=quote.change_pct,
            change_amount=quote.change_amount,
            open_price=quote.last_price,
            high_price=quote.last_price,
            low_price=quote.last_price,
            prev_close=quote.previous_close or quote.last_price,
            volume=0.0,
            amount=0.0,
            timestamp="",
            data_source=self.name,
            source_quality=MarketDataQuality.ESTIMATED.value,
            is_stale=True,
        )
        return ProviderResult(
            quality=MarketDataQuality.ESTIMATED,
            source=self.name,
            data=snapshot,
            message="OpenBB quote is optional estimated fallback.",
        )

    def fetch_intraday_bars(self, symbol: str) -> ProviderResult[list[KlineBar]]:
        return ProviderResult(
            quality=MarketDataQuality.UNAVAILABLE,
            source=self.name,
            message="intraday bars not enabled for OpenBB adapter",
        )

    def fetch_sector_heatmap(self) -> ProviderResult[list[SectorSnapshot]]:
        return ProviderResult(
            quality=MarketDataQuality.UNAVAILABLE,
            source=self.name,
            message="sector heatmap not enabled for OpenBB adapter",
        )
