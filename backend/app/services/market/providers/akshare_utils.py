from __future__ import annotations

from collections.abc import Callable

from app.models.schemas import KlineBar, QuoteSnapshot
from app.services.market.providers.quality import MarketDataQuality
from app.services.market.shared import _safe_str
from app.services.market.shared import _safe_float, guess_market

_ST_NAME_MARKERS = ("ST", "*ST", "退")
_ST_PREFIX_MARKERS = ("退市",)


def bounded_strength(change_pct: float) -> float:
    return round(max(0.0, min(100.0, 50.0 + change_pct * 8.0)), 2)


def extract_industry_names(rows: list[dict[str, object]]) -> list[str]:
    names: list[str] = []
    for row in rows:
        industry = extract_first_value(row, ("板块名称", "行业", "name", "industry"))
        if industry and industry not in names:
            names.append(industry)
    return names


def extract_first_value(row: dict[str, object], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = _safe_str(row.get(key)).strip()
        if value:
            return value
    return ""


def build_sw_category_map(rows: list[dict[str, object]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows:
        raw_code = extract_first_value(row, ("类目编码", "code"))
        name = extract_first_value(row, ("类目名称", "name"))
        if not raw_code or not name:
            continue
        result[raw_code.removeprefix("S")] = name
    return result


def resolve_sw_industry_name(industry_code: str, category_map: dict[str, str]) -> str:
    code = str(industry_code or "").strip().removeprefix("S")
    if not code:
        return ""
    for candidate in (code[:4], code[:6], code[:2], code):
        name = category_map.get(candidate)
        if name:
            return name
    return ""


def is_st_or_delist_name(name: str) -> bool:
    text = str(name or "").strip().upper()
    if not text:
        return False
    return text.startswith(_ST_PREFIX_MARKERS) or any(marker in text for marker in _ST_NAME_MARKERS)


def parse_spot_snapshot_records(
    records: list[dict[str, object]],
    *,
    instrument_type: str,
    source: str,
    normalize_timestamp: Callable[[str], str],
) -> dict[str, QuoteSnapshot]:
    result: dict[str, QuoteSnapshot] = {}
    for row in records:
        symbol = _safe_str(row.get("代码") or row.get("symbol")).strip()
        if not symbol:
            continue
        if symbol.startswith(("sh", "sz", "bj")):
            symbol = symbol[-6:]
        name = _safe_str(row.get("名称") or row.get("name")) or symbol
        latest_price = _safe_float(row.get("最新价") or row.get("最新"))
        prev_close = _safe_float(row.get("昨收") or row.get("昨收价") or row.get("昨收盘"))
        change_amount = _safe_float(row.get("涨跌额"))
        change_pct = _safe_float(row.get("涨跌幅"))
        if not change_amount and latest_price and prev_close:
            change_amount = round(latest_price - prev_close, 4)
        if not change_pct and change_amount and prev_close:
            change_pct = round((change_amount / prev_close) * 100, 4)
        timestamp = normalize_timestamp(
            _safe_str(row.get("时间戳") or row.get("更新时间") or row.get("数据日期"))
        )
        result[symbol] = QuoteSnapshot(
            symbol=symbol,
            name=name,
            market=guess_market(symbol),
            instrument_type=instrument_type,
            last_price=latest_price,
            change_pct=change_pct,
            change_amount=change_amount,
            open_price=_safe_float(row.get("今开") or row.get("开盘价") or row.get("开盘")),
            high_price=_safe_float(row.get("最高") or row.get("最高价")),
            low_price=_safe_float(row.get("最低") or row.get("最低价")),
            prev_close=prev_close,
            volume=_safe_float(row.get("成交量") or row.get("成交量(手)")),
            amount=_safe_float(row.get("成交额")),
            turnover_rate=None,
            volume_ratio=None,
            timestamp=timestamp,
            data_source=source,
            source_quality=MarketDataQuality.FRESH.value,
            is_stale=False,
        )
    return result


def parse_sina_minute_records(records: list[dict[str, object]]) -> list[KlineBar]:
    bars: list[KlineBar] = []
    for row in records:
        open_price = _safe_float(row.get("open"))
        high_price = _safe_float(row.get("high"))
        low_price = _safe_float(row.get("low"))
        close_price = _safe_float(row.get("close"))
        if close_price <= 0:
            continue
        amplitude = round((high_price - low_price) / open_price * 100, 4) if open_price else None
        change_pct = round((close_price - open_price) / open_price * 100, 4) if open_price else None
        bars.append(
            KlineBar(
                timestamp=str(row.get("day"))[:16],
                open=open_price or close_price,
                close=close_price,
                high=high_price or close_price,
                low=low_price or close_price,
                volume=_safe_float(row.get("volume")),
                amount=_safe_float(row.get("amount")),
                amplitude=amplitude,
                change_pct=change_pct,
                turnover=None,
            )
        )
    return bars
