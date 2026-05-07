from __future__ import annotations

from app.models.schemas import KlineBar, QuoteSnapshot, SectorSnapshot
from app.services.market.openbb_adapter import OpenBBDataAdapter
from app.services.market.providers.quality import MarketDataQuality, ProviderResult
from app.services.market.shared import guess_instrument_type, guess_market


class OpenBBMarketProvider:
    name = "openbb"

    def __init__(self, service) -> None:
        self.service = service
        self.adapter = OpenBBDataAdapter(timeout=getattr(service.settings, "market_quote_timeout_seconds", 3))

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

    def fetch_board_breadth_frame(self) -> ProviderResult:
        return ProviderResult(
            quality=MarketDataQuality.UNAVAILABLE,
            source=self.name,
            message="board breadth not enabled for OpenBB adapter",
        )

    def fetch_trade_dates(self) -> ProviderResult:
        return ProviderResult(
            quality=MarketDataQuality.UNAVAILABLE,
            source=self.name,
            message="trade calendar not enabled for OpenBB adapter",
        )

    def fetch_market_emotion_pools(
        self,
        effective_trade_date: str,
        previous_trade_date: str | None = None,
    ) -> ProviderResult:
        return ProviderResult(
            quality=MarketDataQuality.UNAVAILABLE,
            source=self.name,
            message="market emotion pools not enabled for OpenBB adapter",
        )

    def fetch_limit_up_pool(self, trade_date: str) -> ProviderResult:
        return ProviderResult(
            quality=MarketDataQuality.UNAVAILABLE,
            source=self.name,
            message="limit-up pool not enabled for OpenBB adapter",
        )

    def fetch_limit_down_pool(self, trade_date: str) -> ProviderResult:
        return ProviderResult(
            quality=MarketDataQuality.UNAVAILABLE,
            source=self.name,
            message="limit-down pool not enabled for OpenBB adapter",
        )

    def fetch_daily_history(self, symbol: str, start_date: str, end_date: str) -> ProviderResult:
        return ProviderResult(
            quality=MarketDataQuality.UNAVAILABLE,
            source=self.name,
            message="daily history not enabled for OpenBB adapter",
        )

    def fetch_sector_fund_flow_rank(self) -> ProviderResult:
        return self._unavailable("sector fund flow not enabled for OpenBB adapter")

    def fetch_individual_fund_flow(self, symbol: str, market: str) -> ProviderResult:
        return self._unavailable("individual fund flow not enabled for OpenBB adapter")

    def fetch_northbound_fund_flow_summary(self) -> ProviderResult:
        return self._unavailable("northbound fund flow not enabled for OpenBB adapter")

    def fetch_limit_up_snapshot(self) -> ProviderResult:
        return self._unavailable("limit-up snapshot not enabled for OpenBB adapter")

    def fetch_lhb_stock_statistic(self) -> ProviderResult:
        return self._unavailable("lhb statistic not enabled for OpenBB adapter")

    def fetch_stock_notice_report(self, symbol: str) -> ProviderResult:
        return self._unavailable("stock notice report not enabled for OpenBB adapter")

    def fetch_market_events(self, symbol: str) -> ProviderResult:
        return self._unavailable("market events not enabled for OpenBB adapter")

    def _unavailable(self, message: str) -> ProviderResult:
        return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=message)
