from __future__ import annotations

from typing import Any


class ExternalFactorDataError(RuntimeError):
    """Raised when optional external factor data is unavailable."""


def stock_sector_fund_flow_rank() -> Any:
    return _router_data("fetch_sector_fund_flow_rank")


def stock_individual_fund_flow(symbol: str, market: str) -> Any:
    return _router_data("fetch_individual_fund_flow", symbol, market)


def stock_hsgt_fund_flow_summary_em() -> Any:
    return _router_data("fetch_northbound_fund_flow_summary")


def stock_zt_pool_em() -> Any:
    return _router_data("fetch_limit_up_snapshot")


def stock_lhb_stock_statistic_em() -> Any:
    return _router_data("fetch_lhb_stock_statistic")


def stock_notice_report(symbol: str) -> Any:
    return _router_data("fetch_stock_notice_report", symbol)


def _router_data(method_name: str, *args) -> Any:
    try:
        from app.services.market.service import MarketDataService

        router = MarketDataService().provider_router
        result = getattr(router, method_name)(*args)
    except Exception as exc:  # pragma: no cover - optional data source path
        raise ExternalFactorDataError("market provider unavailable") from exc
    if not result.usable or result.data is None:
        raise ExternalFactorDataError(result.message or "external factor data unavailable")
    return result.data
