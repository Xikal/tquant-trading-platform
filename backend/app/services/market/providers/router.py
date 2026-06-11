from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import logging
import time
from typing import Protocol, TypeVar

from app.core.config import get_settings
from app.services.market.providers.circuit import ProviderCircuitConfig, ProviderCircuitRegistry
from app.services.market.providers.priority import order_providers_for_operation, provider_execution_tier
from app.services.market.providers.quality import MarketDataQuality, ProviderResult


T = TypeVar("T")
logger = logging.getLogger(__name__)
_FAST_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="market-provider-fast")
_SLOW_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="market-provider-slow")


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

    def fetch_sector_fund_flow(self, period: str = "today", sector_type: str = "industry", limit: int = 30): ...

    def fetch_individual_fund_flow(self, symbol: str, market: str): ...

    def fetch_northbound_fund_flow_summary(self): ...

    def fetch_limit_up_snapshot(self, trade_date: str = ""): ...

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
        settings = get_settings()
        self.circuits = ProviderCircuitRegistry(
            ProviderCircuitConfig(
                failure_threshold=settings.market_provider_circuit_failure_threshold,
                cooldown_seconds=settings.market_provider_circuit_cooldown_seconds,
                cooldown_second_seconds=settings.market_provider_circuit_cooldown_second_seconds,
                cooldown_max_seconds=settings.market_provider_circuit_cooldown_max_seconds,
                slow_call_ms=settings.market_provider_slow_call_ms,
            )
        )
        self.call_timeout_seconds = max(float(settings.market_provider_call_timeout_seconds or 0), 0.0)

    def fetch_quote(self, symbol: str) -> ProviderResult:
        return self._first_usable("fetch_quote", lambda provider: provider.fetch_quote(symbol))

    def fetch_intraday_bars(self, symbol: str) -> ProviderResult:
        return self._first_usable("fetch_intraday_bars", lambda provider: provider.fetch_intraday_bars(symbol))

    def fetch_sector_heatmap(self) -> ProviderResult:
        return self._first_usable("fetch_sector_heatmap", lambda provider: provider.fetch_sector_heatmap())

    def fetch_board_breadth_frame(self) -> ProviderResult:
        return self._first_usable("fetch_board_breadth_frame", lambda provider: provider.fetch_board_breadth_frame())

    def fetch_trade_dates(self) -> ProviderResult:
        return self._first_usable("fetch_trade_dates", lambda provider: provider.fetch_trade_dates())

    def fetch_market_emotion_pools(
        self,
        effective_trade_date: str,
        previous_trade_date: str | None = None,
    ) -> ProviderResult:
        return self._first_usable(
            "fetch_market_emotion_pools",
            lambda provider: provider.fetch_market_emotion_pools(effective_trade_date, previous_trade_date)
        )

    def fetch_limit_up_pool(self, trade_date: str) -> ProviderResult:
        return self._first_usable("fetch_limit_up_pool", lambda provider: provider.fetch_limit_up_pool(trade_date))

    def fetch_limit_down_pool(self, trade_date: str) -> ProviderResult:
        return self._first_usable("fetch_limit_down_pool", lambda provider: provider.fetch_limit_down_pool(trade_date))

    def fetch_daily_history(self, symbol: str, start_date: str, end_date: str) -> ProviderResult:
        return self._first_usable("fetch_daily_history", lambda provider: provider.fetch_daily_history(symbol, start_date, end_date))

    def fetch_sector_fund_flow_rank(self) -> ProviderResult:
        return self._first_usable("fetch_sector_fund_flow_rank", lambda provider: provider.fetch_sector_fund_flow_rank())

    def fetch_sector_fund_flow(self, period: str = "today", sector_type: str = "industry", limit: int = 30) -> ProviderResult:
        return self._first_usable(
            "fetch_sector_fund_flow",
            lambda provider: provider.fetch_sector_fund_flow(period=period, sector_type=sector_type, limit=limit),
        )

    def fetch_individual_fund_flow(self, symbol: str, market: str) -> ProviderResult:
        return self._first_usable("fetch_individual_fund_flow", lambda provider: provider.fetch_individual_fund_flow(symbol, market))

    def fetch_northbound_fund_flow_summary(self) -> ProviderResult:
        return self._first_usable("fetch_northbound_fund_flow_summary", lambda provider: provider.fetch_northbound_fund_flow_summary())

    def fetch_limit_up_snapshot(self, trade_date: str = "") -> ProviderResult:
        return self._first_usable(
            "fetch_limit_up_snapshot",
            lambda provider: provider.fetch_limit_up_snapshot(trade_date),
        )

    def fetch_lhb_stock_statistic(self) -> ProviderResult:
        return self._first_usable("fetch_lhb_stock_statistic", lambda provider: provider.fetch_lhb_stock_statistic())

    def fetch_stock_notice_report(self, symbol: str) -> ProviderResult:
        return self._first_usable("fetch_stock_notice_report", lambda provider: provider.fetch_stock_notice_report(symbol))

    def fetch_market_events(self, symbol: str) -> ProviderResult:
        return self._first_usable("fetch_market_events", lambda provider: provider.fetch_market_events(symbol))

    def fetch_stock_instrument_rows(self) -> ProviderResult:
        return self._first_usable("fetch_stock_instrument_rows", lambda provider: provider.fetch_stock_instrument_rows())

    def fetch_etf_instrument_rows(self) -> ProviderResult:
        return self._first_usable("fetch_etf_instrument_rows", lambda provider: provider.fetch_etf_instrument_rows())

    def fetch_industry_constituent_map(self) -> ProviderResult:
        return self._first_usable("fetch_industry_constituent_map", lambda provider: provider.fetch_industry_constituent_map())

    def fetch_stock_industry(self, symbol: str) -> ProviderResult:
        return self._first_usable("fetch_stock_industry", lambda provider: provider.fetch_stock_industry(symbol))

    def metrics_snapshot(self) -> dict:
        return self.circuits.snapshot()

    def all_providers_circuit_open(self, operation: str) -> bool:
        if not self.providers:
            return False
        snapshot = self.circuits.snapshot()
        provider_metrics = snapshot.get("providers") if isinstance(snapshot, dict) else {}
        if not isinstance(provider_metrics, dict) or not provider_metrics:
            return False
        for provider in self.providers:
            provider_name = getattr(provider, "name", provider.__class__.__name__)
            metrics = provider_metrics.get(f"{provider_name}:{operation}") or {}
            if not metrics or not metrics.get("circuit_open"):
                return False
        return True

    def _first_usable(self, operation: str, call) -> ProviderResult:
        last_result: ProviderResult | None = None
        for provider in order_providers_for_operation(self.providers, self.circuits.snapshot(), operation):
            provider_name = getattr(provider, "name", provider.__class__.__name__)
            if not self.circuits.can_call(provider_name, operation):
                logger.warning(
                    "market provider circuit open",
                    extra={"component": "market-provider-router", "provider": provider_name},
                )
                last_result = ProviderResult(
                    quality=MarketDataQuality.UNAVAILABLE,
                    source=provider_name,
                    message="provider circuit open",
                )
                continue
            started = time.perf_counter()
            try:
                result = _call_provider(
                    provider=provider,
                    call=call,
                    timeout_seconds=self.call_timeout_seconds,
                )
            except FutureTimeoutError:
                latency_ms = int((time.perf_counter() - started) * 1000)
                message = f"provider call timed out after {self.call_timeout_seconds:.1f}s"
                self.circuits.record(provider_name, operation, ok=False, latency_ms=latency_ms, error=message)
                logger.warning(
                    "market provider call timed out: operation=%s latency_ms=%s",
                    operation,
                    latency_ms,
                    extra={"component": "market-provider-router", "provider": provider_name},
                )
                result = ProviderResult(
                    quality=MarketDataQuality.UNAVAILABLE,
                    source=provider_name,
                    message=message,
                    latency_ms=latency_ms,
                )
            except Exception as exc:
                latency_ms = int((time.perf_counter() - started) * 1000)
                self.circuits.record(provider_name, operation, ok=False, latency_ms=latency_ms, error=str(exc))
                logger.warning(
                    "market provider call failed: operation=%s latency_ms=%s",
                    operation,
                    latency_ms,
                    extra={"component": "market-provider-router", "provider": provider_name},
                )
                result = ProviderResult(
                    quality=MarketDataQuality.UNAVAILABLE,
                    source=provider_name,
                    message=str(exc)[:160],
                    latency_ms=latency_ms,
                )
            latency_ms = int((time.perf_counter() - started) * 1000)
            result = _with_latency(result, latency_ms)
            self.circuits.record(
                provider_name,
                operation,
                ok=result.usable,
                latency_ms=latency_ms,
                error=result.message,
            )
            last_result = result
            if result.usable:
                return result
            logger.info(
                "market provider result not usable: operation=%s quality=%s",
                operation,
                getattr(result.quality, "value", str(result.quality)),
                extra={"component": "market-provider-router", "provider": provider_name},
            )
        return last_result or ProviderResult(
            quality=MarketDataQuality.UNAVAILABLE,
            source="none",
            message="no provider configured",
        )


def _call_provider(*, provider: MarketProvider, call, timeout_seconds: float) -> ProviderResult:
    if timeout_seconds <= 0:
        return call(provider)
    executor = _SLOW_EXECUTOR if provider_execution_tier(provider) == "slow" else _FAST_EXECUTOR
    future = executor.submit(call, provider)
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError:
        future.cancel()
        raise


def _with_latency(result: ProviderResult, latency_ms: int) -> ProviderResult:
    if result.latency_ms:
        return result
    return ProviderResult(
        quality=result.quality,
        source=result.source,
        data=result.data,
        message=result.message,
        latency_ms=latency_ms,
    )
