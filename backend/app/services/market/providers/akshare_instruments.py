from __future__ import annotations

from app.services.market.providers.akshare_utils import (
    build_sw_category_map,
    extract_first_value,
    extract_industry_names,
    is_st_or_delist_name,
    resolve_sw_industry_name,
)
from app.services.market.providers.quality import MarketDataQuality, ProviderResult
from app.services.market.shared import ak


def fetch_stock_instrument_rows(raw_call, provider_name: str) -> ProviderResult[list[dict[str, object]]]:  # noqa: ANN001
    if ak is None:
        return _ak_unavailable(provider_name)
    try:
        frame = raw_call(ak.stock_info_a_code_name, purpose="industry")
    except Exception as exc:
        return _unavailable(provider_name, str(exc))
    rows = frame.to_dict("records") if frame is not None and not getattr(frame, "empty", False) else []
    return ProviderResult(
        quality=MarketDataQuality.FRESH if rows else MarketDataQuality.UNAVAILABLE,
        source=provider_name,
        data=rows or None,
    )


def fetch_etf_instrument_rows(raw_call, provider_name: str) -> ProviderResult[list[dict[str, object]]]:  # noqa: ANN001
    if ak is None:
        return _ak_unavailable(provider_name)
    try:
        frame = raw_call(
            ak.fund_etf_category_sina,
            symbol="ETF基金",
            purpose="industry",
        )
    except Exception as exc:
        return _unavailable(provider_name, str(exc))
    rows = frame.to_dict("records") if frame is not None and not getattr(frame, "empty", False) else []
    return ProviderResult(
        quality=MarketDataQuality.FRESH if rows else MarketDataQuality.UNAVAILABLE,
        source=provider_name,
        data=rows or None,
    )


def fetch_industry_constituent_map(raw_call, provider_name: str) -> ProviderResult[dict[str, str]]:  # noqa: ANN001
    if ak is None:
        return _ak_unavailable(provider_name)
    result = _load_em_industry_constituent_map(raw_call)
    for symbol, industry in _load_sw_industry_constituent_map(raw_call).items():
        result.setdefault(symbol, industry)
    return ProviderResult(
        quality=MarketDataQuality.FRESH if result else MarketDataQuality.UNAVAILABLE,
        source=provider_name,
        data=result or None,
    )


def fetch_stock_industry(raw_call, provider_name: str, symbol: str) -> ProviderResult[str]:  # noqa: ANN001
    if ak is None:
        return _ak_unavailable(provider_name)
    try:
        info_df = raw_call(ak.stock_individual_info_em, symbol=symbol, purpose="industry")
        industry_values = info_df.loc[info_df["item"] == "行业", "value"].tolist()
    except Exception as exc:
        return _unavailable(provider_name, str(exc))
    industry = str(industry_values[0]).strip() if industry_values else ""
    return ProviderResult(
        quality=MarketDataQuality.FRESH if industry else MarketDataQuality.UNAVAILABLE,
        source=provider_name,
        data=industry or None,
    )


def _load_em_industry_constituent_map(raw_call) -> dict[str, str]:  # noqa: ANN001
    try:
        industry_frame = raw_call(ak.stock_board_industry_name_em, purpose="industry")
    except Exception:
        return {}
    industry_names = extract_industry_names(industry_frame.to_dict("records"))
    result: dict[str, str] = {}
    for industry in industry_names:
        try:
            constituents = raw_call(
                ak.stock_board_industry_cons_em,
                symbol=industry,
                purpose="industry",
            )
        except Exception:
            continue
        for record in constituents.to_dict("records"):
            symbol = extract_first_value(record, ("代码", "股票代码", "code", "symbol"))
            name = extract_first_value(record, ("名称", "股票名称", "name", "证券简称"))
            if not symbol or is_st_or_delist_name(name):
                continue
            result.setdefault(symbol, industry)
    return result


def _load_sw_industry_constituent_map(raw_call) -> dict[str, str]:  # noqa: ANN001
    try:
        history_frame = raw_call(ak.stock_industry_clf_hist_sw, purpose="industry")
        category_frame = raw_call(
            ak.stock_industry_category_cninfo,
            symbol="申银万国行业分类标准",
            purpose="industry",
        )
    except Exception:
        return {}
    category_map = build_sw_category_map(category_frame.to_dict("records"))
    latest_by_symbol: dict[str, tuple[str, str, str]] = {}
    for row in history_frame.to_dict("records"):
        symbol = extract_first_value(row, ("symbol", "股票代码", "代码"))
        industry_code = extract_first_value(row, ("industry_code", "行业代码", "类目编码"))
        if not symbol or not industry_code:
            continue
        start_date = extract_first_value(row, ("start_date", "开始日期"))
        update_time = extract_first_value(row, ("update_time", "更新时间"))
        current = latest_by_symbol.get(symbol)
        marker = (start_date, update_time)
        if current is None or marker >= (current[1], current[2]):
            latest_by_symbol[symbol] = (industry_code, start_date, update_time)
    result: dict[str, str] = {}
    for symbol, (industry_code, _, _) in latest_by_symbol.items():
        industry = resolve_sw_industry_name(industry_code, category_map)
        if industry:
            result[symbol] = industry
    return result


def _ak_unavailable(provider_name: str) -> ProviderResult:
    return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=provider_name, message="akshare unavailable")


def _unavailable(provider_name: str, message: str) -> ProviderResult:
    return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=provider_name, message=message[:160])
