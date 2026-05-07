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

    def fetch_board_breadth_frame(self) -> ProviderResult:
        return ProviderResult(
            quality=MarketDataQuality.UNAVAILABLE,
            source=self.name,
            message="board breadth not provided by this adapter",
        )

    def fetch_trade_dates(self) -> ProviderResult:
        return ProviderResult(
            quality=MarketDataQuality.UNAVAILABLE,
            source=self.name,
            message="trade calendar not provided by this adapter",
        )

    def fetch_market_emotion_pools(
        self,
        effective_trade_date: str,
        previous_trade_date: str | None = None,
    ) -> ProviderResult:
        return ProviderResult(
            quality=MarketDataQuality.UNAVAILABLE,
            source=self.name,
            message="market emotion pools not provided by this adapter",
        )

    def fetch_limit_up_pool(self, trade_date: str) -> ProviderResult:
        return ProviderResult(
            quality=MarketDataQuality.UNAVAILABLE,
            source=self.name,
            message="limit-up pool not provided by this adapter",
        )

    def fetch_limit_down_pool(self, trade_date: str) -> ProviderResult:
        return ProviderResult(
            quality=MarketDataQuality.UNAVAILABLE,
            source=self.name,
            message="limit-down pool not provided by this adapter",
        )

    def fetch_daily_history(self, symbol: str, start_date: str, end_date: str) -> ProviderResult:
        return ProviderResult(
            quality=MarketDataQuality.UNAVAILABLE,
            source=self.name,
            message="daily history not provided by this adapter",
        )
