from __future__ import annotations

from math import ceil, floor
from typing import Any

from app.core.timezone import beijing_now_string
from app.models.schema_defs.market import IntradayKeyLevelOut, IntradayKeyLevelResponse
from app.services.low_buy.intraday_confirmation import calculate_intraday_vwap
from app.services.market.go_read_client import load_go_intraday_key_levels
from app.services.market_data import DataSourceError, MarketDataService


class IntradayKeyLevelService:
    def __init__(self, market_data: MarketDataService | None = None) -> None:
        self.market_data = market_data or MarketDataService()

    def build(
        self,
        symbol: str,
        *,
        entry_zone_low: float | None = None,
        entry_zone_high: float | None = None,
        threshold_pct: float = 0.3,
    ) -> IntradayKeyLevelResponse:
        symbol = symbol.strip()
        go_response = load_go_intraday_key_levels(
            symbol,
            entry_zone_low=entry_zone_low,
            entry_zone_high=entry_zone_high,
            threshold_pct=threshold_pct,
        )
        if go_response is not None:
            return go_response
        try:
            quote = self.market_data.get_quote(symbol)
        except Exception:
            return IntradayKeyLevelResponse(
                symbol=symbol,
                updated_at=beijing_now_string(),
                data_quality_text="实时行情不可用，无法计算分时关键位。",
            )
        latest_price = float(getattr(quote, "last_price", 0.0) or 0.0)
        if latest_price <= 0:
            return IntradayKeyLevelResponse(
                symbol=symbol,
                name=str(getattr(quote, "name", "") or ""),
                updated_at=beijing_now_string(),
                data_quality_text="最新价无效，无法计算分时关键位。",
            )
        bars = self._load_bars(symbol)
        vwap = calculate_intraday_vwap(bars) if bars else 0.0
        levels = _build_levels(
            latest_price=latest_price,
            vwap=vwap,
            open_price=float(getattr(quote, "open_price", 0.0) or 0.0),
            prev_close=float(getattr(quote, "prev_close", 0.0) or 0.0),
            entry_zone_low=entry_zone_low,
            entry_zone_high=entry_zone_high,
            threshold_pct=threshold_pct,
        )
        alerts = [level for level in levels if level.alert]
        return IntradayKeyLevelResponse(
            symbol=symbol,
            name=str(getattr(quote, "name", "") or ""),
            updated_at=beijing_now_string(),
            latest_price=round(latest_price, 4),
            vwap=round(vwap, 4),
            entry_zone_low=entry_zone_low,
            entry_zone_high=entry_zone_high,
            alert_threshold_pct=threshold_pct,
            alert_triggered=bool(alerts),
            alert_text=_alert_text(symbol, alerts),
            levels=levels,
            data_quality_text="分时关键位使用实时价、VWAP、开盘价、昨收和整数关口估算。",
        )

    def _load_bars(self, symbol: str) -> list[Any]:
        try:
            return self.market_data.get_intraday_bars(symbol, period="1m", limit=240, allow_slow_fallback=False)
        except (DataSourceError, Exception):
            return []


def _build_levels(
    *,
    latest_price: float,
    vwap: float,
    open_price: float,
    prev_close: float,
    entry_zone_low: float | None,
    entry_zone_high: float | None,
    threshold_pct: float,
) -> list[IntradayKeyLevelOut]:
    raw_levels: list[tuple[str, str, float]] = []
    if vwap > 0:
        raw_levels.append(("vwap", "分时均价 VWAP", vwap))
    if open_price > 0:
        raw_levels.append(("open", "开盘价", open_price))
    if prev_close > 0:
        raw_levels.append(("prev_close", "昨收", prev_close))
    for price in _round_number_levels(latest_price):
        raw_levels.append(("round_number", "整数关口", price))
    if entry_zone_low and entry_zone_low > 0:
        raw_levels.append(("entry_low", "买点区下沿", entry_zone_low))
    if entry_zone_high and entry_zone_high > 0:
        raw_levels.append(("entry_high", "买点区上沿", entry_zone_high))
    return _dedupe_levels(raw_levels, latest_price, threshold_pct)


def _round_number_levels(price: float) -> list[float]:
    step = 0.5 if price < 20 else 1.0
    lower = floor(price / step) * step
    upper = ceil(price / step) * step
    return sorted({round(lower, 2), round(upper, 2)})


def _dedupe_levels(
    raw_levels: list[tuple[str, str, float]],
    latest_price: float,
    threshold_pct: float,
) -> list[IntradayKeyLevelOut]:
    seen: set[tuple[str, float]] = set()
    levels: list[IntradayKeyLevelOut] = []
    for level_type, level_text, price in raw_levels:
        if price <= 0:
            continue
        key = (level_type, round(price, 3))
        if key in seen:
            continue
        seen.add(key)
        distance_pct = (latest_price - price) / max(price, 0.01) * 100
        levels.append(
            IntradayKeyLevelOut(
                level_type=level_type,
                level_text=level_text,
                price=round(price, 4),
                distance_pct=round(distance_pct, 4),
                alert=abs(distance_pct) <= threshold_pct,
            )
        )
    levels.sort(key=lambda item: abs(item.distance_pct))
    return levels


def _alert_text(symbol: str, alerts: list[IntradayKeyLevelOut]) -> str:
    if not alerts:
        return ""
    primary = alerts[0]
    return f"{symbol} 接近{primary.level_text} {primary.price:.3f}，偏离 {primary.distance_pct:+.2f}%。"
