from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.models.schema_defs.key_levels import KeyLevelCandidate, KeyLevelResult
from app.services.key_levels.linkage import apply_three_layer_linkage
from app.services.key_levels.materialization import read_cached_key_level


@dataclass(frozen=True)
class KeyLevelContext:
    result: KeyLevelResult
    evidence: list[str]
    support_broken: bool
    near_support: bool
    near_resistance: bool
    position_percentile: float | None
    invalid_condition: str


def load_stock_key_level_context(
    db: Session,
    symbol: str,
    *,
    trade_date: date | str | None = None,
    latest_price: float | None = None,
) -> KeyLevelContext | None:
    result = read_cached_key_level(db, scope="stock", key=symbol, trade_date=_trade_date_text(trade_date))
    if result is None:
        return None
    result = apply_three_layer_linkage(db, result, trade_date=_trade_date_text(trade_date) or result.trade_date)
    if result.data_quality in {"insufficient", "stale", "blocked"}:
        return None
    price = float(latest_price or result.latest_price or 0.0)
    support_low = _number(result.support_zone_low)
    support_high = _number(result.support_zone_high or result.support_price)
    resistance_low = _number(result.resistance_zone_low or result.resistance_price)
    resistance_high = _number(result.resistance_zone_high or result.resistance_price)
    support_broken = bool(price and support_low and price < support_low)
    near_support = bool(price and support_low and support_high and support_low <= price <= support_high * 1.015)
    near_resistance = bool(price and resistance_low and resistance_high and resistance_low * 0.985 <= price <= resistance_high)
    evidence = _evidence(result)
    return KeyLevelContext(
        result=result,
        evidence=evidence,
        support_broken=support_broken,
        near_support=near_support,
        near_resistance=near_resistance,
        position_percentile=_position_percentile(price, support_low, resistance_high),
        invalid_condition=_invalid_condition(result),
    )


def key_level_missing_evidence(symbol: str, trade_date: date | str | None = None) -> list[str]:
    date_text = _trade_date_text(trade_date)
    if date_text:
        return [f"AKeyLevel 缓存缺失：{symbol} @ {date_text}", "关键位缺失时不推断支撑/压力"]
    return [f"AKeyLevel 缓存缺失：{symbol}", "关键位缺失时不推断支撑/压力"]


def _trade_date_text(value: date | str | None) -> str | None:
    if value is None:
        return None
    return value.isoformat() if isinstance(value, date) else str(value)[:10]


def _number(value: float | int | None) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if number > 0 else None


def _position_percentile(price: float, support_low: float | None, resistance_high: float | None) -> float | None:
    if not price or not support_low or not resistance_high or resistance_high <= support_low:
        return None
    return max(0.0, min(1.0, (price - support_low) / (resistance_high - support_low)))


def _evidence(result: KeyLevelResult) -> list[str]:
    evidence = [
        f"AKeyLevel {result.trade_date} · data_quality={result.data_quality}",
    ]
    if result.support_price:
        evidence.append(f"支撑 {result.support_price:.2f}，强度 {result.support_strength}")
    if result.resistance_price:
        evidence.append(f"压力 {result.resistance_price:.2f}，强度 {result.resistance_strength}")
    invalid = _invalid_condition(result)
    if invalid:
        evidence.append(f"失效条件：{invalid}")
    evidence.extend(result.warnings[:2])
    return evidence


def _invalid_condition(result: KeyLevelResult) -> str:
    supports = [item for item in result.key_level_candidates if item.direction == "support"]
    supports.sort(key=_support_sort_key, reverse=True)
    if supports:
        return supports[0].invalid_condition or _candidate_invalid_fallback(supports[0])
    return ""


def _support_sort_key(item: KeyLevelCandidate) -> tuple[int, float]:
    return int(item.strength_score or 0), float(item.price or 0.0)


def _candidate_invalid_fallback(item: KeyLevelCandidate) -> str:
    if item.invalidate_below:
        return f"有效跌破 {item.invalidate_below:.2f}"
    return "等待后续观察"
