from __future__ import annotations

from typing import Any


class ExternalFactorDataError(RuntimeError):
    """Raised when optional external factor data is unavailable."""


def stock_sector_fund_flow_rank() -> Any:
    ak = _akshare()
    return ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")


def stock_individual_fund_flow(symbol: str, market: str) -> Any:
    ak = _akshare()
    return ak.stock_individual_fund_flow(stock=symbol, market=market)


def stock_hsgt_fund_flow_summary_em() -> Any:
    ak = _akshare()
    return ak.stock_hsgt_fund_flow_summary_em()


def stock_zt_pool_em() -> Any:
    ak = _akshare()
    return ak.stock_zt_pool_em()


def stock_lhb_stock_statistic_em() -> Any:
    ak = _akshare()
    return ak.stock_lhb_stock_statistic_em(symbol="近一月")


def stock_notice_report(symbol: str) -> Any:
    ak = _akshare()
    return ak.stock_notice_report(symbol=symbol)


def _akshare() -> Any:
    try:
        import akshare as ak  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise ExternalFactorDataError("akshare unavailable") from exc
    return ak
