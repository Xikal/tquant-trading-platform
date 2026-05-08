from __future__ import annotations

from typing import Protocol, TypeVar

from app.services.market.providers.quality import MarketDataQuality, ProviderResult


T = TypeVar("T")


class MarketProvider(Protocol):
    name: str

    def fetch_quote(self, symbol: str): ...

    def fetch_intraday_bars(self, symbol: str): ...

    def fetch_sector_heatmap(self): ...

    def fetch_board_breadth_frame(self): ...

    def fetch_trade_dates(self): ...

    def fetch_market_emotion_pools(self, effective_trade_date: str, previous_trade_date: str | None = None): ...

    def fetch_limit_up_pool(self, trade_date: str): ...

    def fetch_limit_down_pool(self, trade_date: str): ...

    def fetch_daily_history(self, symbol: str, start_date: str, end_date: str): ...

    def fetch_sector_fund_flow_rank(self): ...

    def fetch_individual_fund_flow(self, symbol: str, market: str): ...

    def fetch_northbound_fund_flow_summary(self): ...

    def fetch_limit_up_snapshot(self): ...

    def fetch_lhb_stock_statistic(self): ...

    def fetch_stock_notice_report(self, symbol: str): ...

    def fetch_market_events(self, symbol: str): ...

    def fetch_stock_instrument_rows(self): ...

    def fetch_etf_instrument_rows(self): ...

    def fetch_industry_constituent_map(self): ...

    def fetch_stock_industry(self, symbol: str): ...


class MarketProviderRouter:
    def __init__(self, providers: list[MarketProvider]) -> None:
        self.providers = providers

    def fetch_quote(self, symbol: str) -> ProviderResult:
        return self._first_usable(lambda provider: provider.fetch_quote(symbol))

    def fetch_intraday_bars(self, symbol: str) -> ProviderResult:
        return self._first_usable(lambda provider: provider.fetch_intraday_bars(symbol))

    def fetch_sector_heatmap(self) -> ProviderResult:
        return self._first_usable(lambda provider: provider.fetch_sector_heatmap())

    def fetch_board_breadth_frame(self) -> ProviderResult:
        return self._first_usable(lambda provider: provider.fetch_board_breadth_frame())

    def fetch_trade_dates(self) -> ProviderResult:
        return self._first_usable(lambda provider: provider.fetch_trade_dates())

    def fetch_market_emotion_pools(
        self,
        effective_trade_date: str,
        previous_trade_date: str | None = None,
    ) -> ProviderResult:
        return self._first_usable(
            lambda provider: provider.fetch_market_emotion_pools(effective_trade_date, previous_trade_date)
        )

    def fetch_limit_up_pool(self, trade_date: str) -> ProviderResult:
        return self._first_usable(lambda provider: provider.fetch_limit_up_pool(trade_date))

    def fetch_limit_down_pool(self, trade_date: str) -> ProviderResult:
        return self._first_usable(lambda provider: provider.fetch_limit_down_pool(trade_date))

    def fetch_daily_history(self, symbol: str, start_date: str, end_date: str) -> ProviderResult:
        return self._first_usable(lambda provider: provider.fetch_daily_history(symbol, start_date, end_date))

    def fetch_sector_fund_flow_rank(self) -> ProviderResult:
        return self._first_usable(lambda provider: provider.fetch_sector_fund_flow_rank())

    def fetch_individual_fund_flow(self, symbol: str, market: str) -> ProviderResult:
        return self._first_usable(lambda provider: provider.fetch_individual_fund_flow(symbol, market))

    def fetch_northbound_fund_flow_summary(self) -> ProviderResult:
        return self._first_usable(lambda provider: provider.fetch_northbound_fund_flow_summary())

    def fetch_limit_up_snapshot(self) -> ProviderResult:
        return self._first_usable(lambda provider: provider.fetch_limit_up_snapshot())

    def fetch_lhb_stock_statistic(self) -> ProviderResult:
        return self._first_usable(lambda provider: provider.fetch_lhb_stock_statistic())

    def fetch_stock_notice_report(self, symbol: str) -> ProviderResult:
        return self._first_usable(lambda provider: provider.fetch_stock_notice_report(symbol))

    def fetch_market_events(self, symbol: str) -> ProviderResult:
        return self._first_usable(lambda provider: provider.fetch_market_events(symbol))

    def fetch_stock_instrument_rows(self) -> ProviderResult:
        return self._first_usable(lambda provider: provider.fetch_stock_instrument_rows())

    def fetch_etf_instrument_rows(self) -> ProviderResult:
        return self._first_usable(lambda provider: provider.fetch_etf_instrument_rows())

    def fetch_industry_constituent_map(self) -> ProviderResult:
        return self._first_usable(lambda provider: provider.fetch_industry_constituent_map())

    def fetch_stock_industry(self, symbol: str) -> ProviderResult:
        return self._first_usable(lambda provider: provider.fetch_stock_industry(symbol))

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
