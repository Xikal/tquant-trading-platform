from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

_SECTOR_FLOW_CACHE: dict[str, tuple[float, dict[str, float]]] = {}
_BIG_ORDER_CACHE: dict[str, tuple[float, dict[str, float]]] = {}
_STOCK_NOTICE_CACHE: dict[str, tuple[float, bool]] = {}

_SECTOR_FLOW_TTL_SECONDS = 600
_BIG_ORDER_TTL_SECONDS = 300
_STOCK_NOTICE_TTL_SECONDS = 1800


def resolve_sector_flow_ranks() -> dict[str, float]:
    """获取板块资金流向排名分；失败时软降级为空，不阻断筛选。"""

    cached = _read_cache(_SECTOR_FLOW_CACHE, "daily")
    if cached is not None:
        return cached
    try:
        import akshare as ak  # type: ignore

        frame = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
    except Exception as exc:  # pragma: no cover - external source
        logger.warning("sector fund flow fetch failed: %s", exc)
        return {}
    if frame is None or frame.empty:
        return {}
    sorted_frame = frame.sort_values("主力净流入-净额", ascending=False)
    total = len(sorted_frame)
    ranks: dict[str, float] = {}
    for index, (_, row) in enumerate(sorted_frame.iterrows()):
        name = str(row.get("名称", ""))
        if not name:
            continue
        percentile = index / max(total, 1)
        if percentile <= 0.1:
            score = 3.0
        elif percentile <= 0.3:
            score = 2.0 - (percentile - 0.1) / 0.2
        elif percentile <= 0.5:
            score = 1.0 - (percentile - 0.3) / 0.4
        else:
            score = 0.0
        ranks[name] = round(max(0.0, score), 2)
    _write_cache(_SECTOR_FLOW_CACHE, "daily", ranks, _SECTOR_FLOW_TTL_SECONDS)
    return ranks


def evaluate_big_order_flow_factor(symbol: str, retracement_days: int) -> float:
    flows = resolve_big_order_flow(symbol=symbol, retracement_days=retracement_days)
    if not flows:
        return 0.0
    score = 0.0
    big_ratio = flows.get("big_order_net_inflow_ratio", 0.0)
    super_big_ratio = flows.get("super_big_net_inflow_ratio", 0.0)
    retail_ratio = flows.get("retail_net_inflow_ratio", 0.0)
    if big_ratio >= 5.0:
        score += 2.5
    elif big_ratio >= 2.0:
        score += 1.5
    elif big_ratio >= 0:
        score += 0.5
    if super_big_ratio >= 5.0:
        score += 1.5
    if retail_ratio >= 10.0:
        score -= 2.0
    elif retail_ratio >= 5.0:
        score -= 1.0
    if big_ratio >= 2.0 and super_big_ratio >= 2.0:
        score += 1.0
    return round(max(0.0, min(5.0, score)), 2)


def resolve_big_order_flow(symbol: str, retracement_days: int) -> dict[str, float]:
    cached = _read_cache(_BIG_ORDER_CACHE, symbol)
    if cached is not None:
        return cached
    market = "sh" if symbol.startswith(("5", "6", "9")) else "sz"
    if symbol.startswith("8"):
        market = "bj"
    try:
        import akshare as ak  # type: ignore

        frame = ak.stock_individual_fund_flow(stock=symbol, market=market)
    except Exception as exc:  # pragma: no cover - external source
        logger.warning("big order flow fetch failed for %s: %s", symbol, exc)
        return {}
    if frame is None or frame.empty:
        return {}
    recent = frame.tail(max(retracement_days + 3, 5))
    result = {
        "big_order_net_inflow_ratio": _mean_column(recent, "大单净流入-净占比"),
        "super_big_net_inflow_ratio": _mean_column(recent, "超大单净流入-净占比"),
        "retail_net_inflow_ratio": _mean_column(recent, "小单净流入-净占比"),
    }
    _write_cache(_BIG_ORDER_CACHE, symbol, result, _BIG_ORDER_TTL_SECONDS)
    return result


def evaluate_event_risk_factor(symbol: str) -> float:
    return 0.0 if resolve_stock_notice_risk(symbol) else 1.0


def resolve_stock_notice_risk(symbol: str) -> bool:
    cached = _read_cache(_STOCK_NOTICE_CACHE, symbol)
    if cached is not None:
        return cached
    try:
        import akshare as ak  # type: ignore

        frame = ak.stock_notice_report(symbol=symbol)
    except Exception:  # pragma: no cover - external source
        _write_cache(_STOCK_NOTICE_CACHE, symbol, False, _STOCK_NOTICE_TTL_SECONDS)
        return False
    if frame is None or frame.empty:
        _write_cache(_STOCK_NOTICE_CACHE, symbol, False, _STOCK_NOTICE_TTL_SECONDS)
        return False
    title_column = next((column for column in frame.columns if "标题" in str(column) or "title" in str(column).lower()), None)
    has_risk = False
    if title_column:
        keywords = ("减持", "问询", "警示", "处罚", "亏损", "退市", "立案", "调查", "预亏", "质押", "冻结", "诉讼")
        has_risk = any(any(keyword in str(row[title_column]) for keyword in keywords) for _, row in frame.head(10).iterrows())
    _write_cache(_STOCK_NOTICE_CACHE, symbol, has_risk, _STOCK_NOTICE_TTL_SECONDS)
    return has_risk


def _mean_column(frame, column: str) -> float:
    if column not in frame.columns:
        return 0.0
    try:
        return round(float(frame[column].astype(float).mean()), 2)
    except Exception:
        return 0.0


def _read_cache(cache: dict, key: str):
    cached = cache.get(key)
    if not cached:
        return None
    expires_at, value = cached
    if expires_at <= time.monotonic():
        cache.pop(key, None)
        return None
    return value


def _write_cache(cache: dict, key: str, value, ttl_seconds: int) -> None:
    cache[key] = (time.monotonic() + ttl_seconds, value)
