from __future__ import annotations

import logging
import threading
import time

from app.services.market import external_factors
from app.services.low_buy.external_factor_cache import (
    get_or_load_ttl_cache,
    read_ttl_cache,
    write_ttl_cache,
)

logger = logging.getLogger(__name__)

_SECTOR_FLOW_CACHE: dict[str, tuple[float, dict[str, float]]] = {}
_BIG_ORDER_CACHE: dict[str, tuple[float, dict[str, float]]] = {}
_STOCK_NOTICE_CACHE: dict[str, tuple[float, bool]] = {}
_NORTH_FLOW_CACHE: dict[str, tuple[float, float]] = {}
_LIMIT_UP_POOL_CACHE: dict[str, tuple[float, dict[str, float]]] = {}
_DRAGON_BOARD_CACHE: dict[str, tuple[float, dict[str, float]]] = {}
_CACHE_LOCK = threading.RLock()

_SECTOR_FLOW_TTL_SECONDS = 600
_BIG_ORDER_TTL_SECONDS = 300
_STOCK_NOTICE_TTL_SECONDS = 1800
_NORTH_FLOW_TTL_SECONDS = 600
_LIMIT_UP_POOL_TTL_SECONDS = 180
_DRAGON_BOARD_TTL_SECONDS = 1800


def resolve_sector_flow_ranks() -> dict[str, float]:
    """获取板块资金流向排名分；失败时软降级为空，不阻断筛选。"""

    try:
        return get_or_load_ttl_cache(
            _SECTOR_FLOW_CACHE,
            _CACHE_LOCK,
            namespace="sector_flow",
            key="daily",
            loader=_load_sector_flow_ranks,
            ttl_seconds=_SECTOR_FLOW_TTL_SECONDS,
            failure_value={},
        )
    except Exception as exc:  # pragma: no cover - external source
        logger.warning("sector fund flow fetch failed: %s", exc)
        return {}


def _load_sector_flow_ranks() -> dict[str, float]:
    try:
        source_data = external_factors.stock_sector_fund_flow_rank()
    except Exception as exc:  # pragma: no cover - external source
        raise RuntimeError(str(exc)) from exc
    typed_items = getattr(source_data, "items", None)
    if isinstance(typed_items, list):
        return _sector_flow_ranks_from_items(typed_items)
    frame = source_data
    if frame is None or frame.empty:
        return {}
    flow_column = _find_column(frame, ("主力净流入-净额", "主力净流入", "净流入-净额", "净额"))
    name_column = _find_column(frame, ("名称", "板块名称", "行业名称"))
    if not flow_column or not name_column:
        logger.warning("sector fund flow columns changed: %s", list(frame.columns))
        return {}
    sorted_frame = (
        frame.assign(_sector_flow_value=frame[flow_column].map(_to_float))
        .sort_values("_sector_flow_value", ascending=False)
    )
    total = len(sorted_frame)
    ranks: dict[str, float] = {}
    for index, (_, row) in enumerate(sorted_frame.iterrows()):
        name = str(row.get(name_column, ""))
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
    return ranks


def _sector_flow_ranks_from_items(items: list) -> dict[str, float]:
    sorted_items = sorted(items, key=lambda item: _to_float(getattr(item, "net_flow", 0.0)), reverse=True)
    total = len(sorted_items)
    ranks: dict[str, float] = {}
    for index, item in enumerate(sorted_items):
        name = str(getattr(item, "sector_name", ""))
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
    try:
        return get_or_load_ttl_cache(
            _BIG_ORDER_CACHE,
            _CACHE_LOCK,
            namespace="big_order",
            key=symbol,
            loader=lambda: _load_big_order_flow(symbol=symbol, retracement_days=retracement_days),
            ttl_seconds=_BIG_ORDER_TTL_SECONDS,
            failure_value={},
        )
    except Exception as exc:  # pragma: no cover - external source
        logger.warning("big order flow fetch failed for %s: %s", symbol, exc)
        return {}


def _load_big_order_flow(symbol: str, retracement_days: int) -> dict[str, float]:
    market = "sh" if symbol.startswith(("5", "6", "9")) else "sz"
    if symbol.startswith("8"):
        market = "bj"
    try:
        frame = external_factors.stock_individual_fund_flow(symbol=symbol, market=market)
    except Exception as exc:  # pragma: no cover - external source
        raise RuntimeError(str(exc)) from exc
    if frame is None or frame.empty:
        return {}
    recent = frame.tail(max(retracement_days + 3, 5))
    result = {
        "big_order_net_inflow_ratio": _mean_column(recent, "大单净流入-净占比"),
        "super_big_net_inflow_ratio": _mean_column(recent, "超大单净流入-净占比"),
        "retail_net_inflow_ratio": _mean_column(recent, "小单净流入-净占比"),
    }
    return result


def evaluate_event_risk_factor(symbol: str) -> float:
    return 0.0 if resolve_stock_notice_risk(symbol) else 1.0


def evaluate_north_flow_factor(trade_date: str = "") -> float:
    """北向资金环境因子。

    免费数据只能作为市场环境辅助，不直接改变买点。返回值为正向加分，
    北向大幅净流出时返回 0，避免制造虚假信心。
    """

    net_inflow = resolve_north_flow_net_inflow(trade_date)
    if net_inflow >= 80:
        return 2.0
    if net_inflow >= 30:
        return 1.2
    if net_inflow > 0:
        return 0.5
    return 0.0


def evaluate_limit_up_quality_factor(symbol: str, trade_date: str = "") -> float:
    pool = resolve_limit_up_pool_quality(trade_date)
    return pool.get(symbol, 0.0)


def evaluate_dragon_board_factor(symbol: str) -> float:
    return resolve_dragon_board_scores().get(symbol, 0.0)


def evaluate_pre_market_auction_factor(_symbol: str) -> float:
    """预留集合竞价因子。

    免费公开源对逐股竞价量价稳定性不足，当前不使用伪数据。
    """

    return 0.0


def evaluate_margin_balance_factor(_symbol: str) -> float:
    """融资融券数据通常为日频，不能冒充实时因子。"""

    return 0.0


def evaluate_block_trade_premium_factor(_symbol: str) -> float:
    return 0.0


def evaluate_earnings_surprise_factor(symbol: str) -> float:
    return 0.0


def evaluate_insider_trade_factor(symbol: str) -> float:
    return 0.0


def evaluate_short_balance_factor(_symbol: str) -> float:
    return 0.0


def resolve_north_flow_net_inflow(trade_date: str = "") -> float:
    try:
        return float(get_or_load_ttl_cache(
            _NORTH_FLOW_CACHE,
            _CACHE_LOCK,
            namespace="north_flow",
            key=trade_date or "latest",
            loader=lambda: _load_north_flow_net_inflow(trade_date),
            ttl_seconds=_NORTH_FLOW_TTL_SECONDS,
            failure_value=0.0,
        ))
    except Exception as exc:  # pragma: no cover - external source
        logger.warning("northbound fund flow fetch failed: %s", exc)
        return 0.0


def _load_north_flow_net_inflow(trade_date: str = "") -> float:
    try:
        frame = external_factors.stock_hsgt_fund_flow_summary_em()
    except Exception as exc:  # pragma: no cover - external source
        raise RuntimeError(str(exc)) from exc
    if frame is None or frame.empty:
        return 0.0
    try:
        north_rows = frame[frame["资金方向"].astype(str).str.contains("北向", na=False)]
        if trade_date and "交易日" in north_rows.columns:
            north_rows = north_rows[north_rows["交易日"].astype(str) == trade_date]
        value = float(north_rows["成交净买额"].astype(float).sum())
    except Exception:
        value = 0.0
    return round(value, 2)


def resolve_limit_up_pool_quality(trade_date: str = "") -> dict[str, float]:
    try:
        return get_or_load_ttl_cache(
            _LIMIT_UP_POOL_CACHE,
            _CACHE_LOCK,
            namespace="limit_up_pool",
            key=trade_date or "latest",
            loader=lambda: _load_limit_up_pool_quality(trade_date),
            ttl_seconds=_LIMIT_UP_POOL_TTL_SECONDS,
            failure_value={},
        )
    except Exception as exc:  # pragma: no cover - external source
        logger.warning("limit-up pool fetch failed: %s", exc)
        return {}


def _load_limit_up_pool_quality(trade_date: str = "") -> dict[str, float]:
    try:
        frame = external_factors.stock_zt_pool_em(trade_date)
    except Exception as exc:  # pragma: no cover - external source
        raise RuntimeError(str(exc)) from exc
    if frame is None or frame.empty:
        return {}
    result: dict[str, float] = {}
    for row in frame.to_dict("records"):
        symbol = str(row.get("代码") or "").strip()
        if not symbol:
            continue
        seal_amount = _to_float(row.get("封单资金") or row.get("封板资金"))
        first_time = str(row.get("首次封板时间") or "")
        open_count = _to_float(row.get("炸板次数") or row.get("开板次数"))
        score = 1.0
        if seal_amount >= 1_000_000_000:
            score += 1.5
        elif seal_amount >= 300_000_000:
            score += 0.8
        if first_time and first_time <= "100000":
            score += 0.6
        if open_count <= 1:
            score += 0.4
        result[symbol] = round(min(score, 3.0), 2)
    return result


def resolve_dragon_board_scores() -> dict[str, float]:
    try:
        return get_or_load_ttl_cache(
            _DRAGON_BOARD_CACHE,
            _CACHE_LOCK,
            namespace="dragon_board",
            key="month",
            loader=_load_dragon_board_scores,
            ttl_seconds=_DRAGON_BOARD_TTL_SECONDS,
            failure_value={},
        )
    except Exception as exc:  # pragma: no cover - external source
        logger.warning("dragon board statistics fetch failed: %s", exc)
        return {}


def _load_dragon_board_scores() -> dict[str, float]:
    try:
        frame = external_factors.stock_lhb_stock_statistic_em()
    except Exception as exc:  # pragma: no cover - external source
        raise RuntimeError(str(exc)) from exc
    if frame is None or frame.empty:
        return {}
    result: dict[str, float] = {}
    for row in frame.to_dict("records"):
        symbol = str(row.get("代码") or "").strip()
        if not symbol:
            continue
        list_count = _to_float(row.get("上榜次数"))
        net_buy = _to_float(row.get("龙虎榜净买额"))
        inst_net_buy = _to_float(row.get("机构买入净额"))
        score = 0.0
        if list_count >= 3:
            score += 0.6
        if net_buy > 0:
            score += min(net_buy / 500_000_000, 1.4)
        if inst_net_buy > 0:
            score += min(inst_net_buy / 300_000_000, 1.0)
        if score > 0:
            result[symbol] = round(min(score, 3.0), 2)
    return result


def resolve_stock_notice_risk(symbol: str) -> bool:
    cached = _read_cache(_STOCK_NOTICE_CACHE, symbol)
    if cached is not None:
        return cached
    try:
        frame = external_factors.stock_notice_report(symbol=symbol)
    except Exception:  # pragma: no cover - external source
        _write_cache(_STOCK_NOTICE_CACHE, symbol, True, _STOCK_NOTICE_TTL_SECONDS)
        return True
    if frame is None or frame.empty:
        _write_cache(_STOCK_NOTICE_CACHE, symbol, True, _STOCK_NOTICE_TTL_SECONDS)
        return True
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
        values = frame[column].map(_to_float)
        return round(float(values.mean()), 2)
    except Exception:
        return 0.0

def _to_float(value) -> float:
    try:
        if value in (None, "", "-", "--"):
            return 0.0
        text = str(value).strip().replace(",", "").replace("%", "").replace("元", "")
        multiplier = 1.0
        if "亿" in text:
            multiplier = 100_000_000.0
            text = text.replace("亿", "")
        elif "万" in text:
            multiplier = 10_000.0
            text = text.replace("万", "")
        return float(text) * multiplier
    except (TypeError, ValueError):
        return 0.0


def _find_column(frame, candidates: tuple[str, ...]) -> str | None:
    columns = [str(column) for column in frame.columns]
    for candidate in candidates:
        if candidate in columns:
            return candidate
    normalized = {column.replace(" ", "").replace("_", "").lower(): column for column in columns}
    for candidate in candidates:
        key = candidate.replace(" ", "").replace("_", "").lower()
        for normalized_column, original_column in normalized.items():
            if key in normalized_column or normalized_column in key:
                return original_column
    return None


def _read_cache(cache: dict, key: str):
    return read_ttl_cache(cache, _CACHE_LOCK, key)


def _write_cache(cache: dict, key: str, value, ttl_seconds: int) -> None:
    write_ttl_cache(cache, _CACHE_LOCK, key, value, ttl_seconds)
