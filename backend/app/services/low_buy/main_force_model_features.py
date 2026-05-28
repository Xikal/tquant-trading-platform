from __future__ import annotations

import math
from typing import Any, Iterable

from app.services.low_buy.main_force_model_schema import MainForceFeatureSnapshot


def build_main_force_features(
    history_rows: Iterable[Any],
    *,
    symbol: str,
    name: str = "",
    as_of_date: str,
    strategy_key: str = "",
    market_state: str = "",
    sector_strength: float = 0.0,
    market_strength: float = 0.0,
    data_quality: str = "fresh",
) -> MainForceFeatureSnapshot:
    rows = [_normalize_row(row) for row in history_rows]
    rows = [row for row in rows if row["trade_date"] and row["trade_date"] <= as_of_date]
    rows.sort(key=lambda item: item["trade_date"])
    if len(rows) < 20:
        return MainForceFeatureSnapshot(
            symbol=symbol,
            name=name,
            strategy_key=strategy_key,
            as_of_date=as_of_date,
            max_source_date=rows[-1]["trade_date"] if rows else "",
            data_quality="unavailable" if not rows else data_quality,
            risk_flags=["历史日线不足，不能判断主力结构。"],
        )

    closes = [row["close_price"] for row in rows]
    highs = [row["high_price"] for row in rows]
    lows = [row["low_price"] for row in rows]
    amounts = [row["amount"] for row in rows]
    pct_changes = [row["pct_chg"] for row in rows]
    latest = rows[-1]
    close = closes[-1]
    ma5 = _mean(closes[-5:])
    ma10 = _mean(closes[-10:])
    ma20 = _mean(closes[-20:])
    ma60 = _mean(closes[-60:]) if len(closes) >= 60 else _mean(closes)
    high20 = max(highs[-20:])
    low20 = min(lows[-20:])
    high60 = max(highs[-60:]) if len(highs) >= 60 else max(highs)
    low60 = min(lows[-60:]) if len(lows) >= 60 else min(lows)
    previous_20_high = max(closes[-21:-1]) if len(closes) >= 21 else max(closes[:-1] or closes)
    day_range = latest["high_price"] - latest["low_price"]
    close_position_ratio = (close - latest["low_price"]) / day_range if day_range > 0 else 0.5
    upper_shadow_ratio = (latest["high_price"] - max(latest["open_price"], close)) / day_range if day_range > 0 else 0.0
    lower_shadow_ratio = (min(latest["open_price"], close) - latest["low_price"]) / day_range if day_range > 0 else 0.0
    drawdown_10 = _drawdown_pct(closes[-10:])
    risk_flags = _risk_flags(
        latest=latest,
        close=close,
        ma20=ma20,
        amount_ratio_1d_20d=_ratio(latest["amount"], _mean(amounts[-20:])),
        upper_shadow_ratio=upper_shadow_ratio,
        market_state=market_state,
        sector_strength=sector_strength,
        data_quality=data_quality,
    )
    values = {
        "position_60d": _position(close, low60, high60),
        "range_20d_pct": _pct(high20, low20),
        "volatility_20d": _stdev(pct_changes[-20:]),
        "drawdown_10d_pct": drawdown_10,
        "amount_ratio_1d_20d": _ratio(latest["amount"], _mean(amounts[-20:])),
        "amount_ratio_5d_20d": _ratio(_mean(amounts[-5:]), _mean(amounts[-20:])),
        "amount_ratio_20d_60d": _ratio(_mean(amounts[-20:]), _mean(amounts[-60:] if len(amounts) >= 60 else amounts)),
        "close_position_ratio": close_position_ratio,
        "lower_shadow_ratio": lower_shadow_ratio,
        "upper_shadow_ratio": upper_shadow_ratio,
        "sector_strength": float(sector_strength or 0.0),
        "market_strength": float(market_strength or 0.0),
    }
    return MainForceFeatureSnapshot(
        symbol=symbol,
        name=name,
        strategy_key=strategy_key,
        as_of_date=as_of_date,
        max_source_date=latest["trade_date"],
        data_quality=data_quality,
        close_price=round(close, 4),
        ma5=round(ma5, 4),
        ma10=round(ma10, 4),
        ma20=round(ma20, 4),
        ma60=round(ma60, 4),
        position_60d=round(values["position_60d"], 4),
        range_20d_pct=round(values["range_20d_pct"], 4),
        volatility_20d=round(values["volatility_20d"], 4),
        drawdown_10d_pct=round(drawdown_10, 4),
        amount_ratio_1d_20d=round(values["amount_ratio_1d_20d"], 4),
        amount_ratio_5d_20d=round(values["amount_ratio_5d_20d"], 4),
        amount_ratio_20d_60d=round(values["amount_ratio_20d_60d"], 4),
        close_position_ratio=round(close_position_ratio, 4),
        lower_shadow_ratio=round(lower_shadow_ratio, 4),
        upper_shadow_ratio=round(upper_shadow_ratio, 4),
        reclaim_ma10=close >= ma10,
        reclaim_ma20=close >= ma20,
        platform_reclaim_20d=close >= previous_20_high * 0.995,
        trend_above_ma60=close >= ma60,
        market_state=market_state,
        sector_strength=float(sector_strength or 0.0),
        market_strength=float(market_strength or 0.0),
        risk_flags=risk_flags,
        feature_values={key: round(float(value), 6) for key, value in values.items()},
    )


def _normalize_row(row: Any) -> dict[str, Any]:
    getter = row.get if isinstance(row, dict) else lambda key, default=None: getattr(row, key, default)
    return {
        "trade_date": str(getter("trade_date", "") or ""),
        "open_price": _float(getter("open_price", 0.0)),
        "close_price": _float(getter("close_price", 0.0)),
        "high_price": _float(getter("high_price", 0.0)),
        "low_price": _float(getter("low_price", 0.0)),
        "volume": _float(getter("volume", 0.0)),
        "amount": _float(getter("amount", 0.0)),
        "pct_chg": _float(getter("pct_chg", 0.0)),
    }


def _risk_flags(
    *,
    latest: dict[str, Any],
    close: float,
    ma20: float,
    amount_ratio_1d_20d: float,
    upper_shadow_ratio: float,
    market_state: str,
    sector_strength: float,
    data_quality: str,
) -> list[str]:
    flags: list[str] = []
    if data_quality not in {"fresh", "verified"}:
        flags.append(f"数据质量为 {data_quality}，只允许旁路观察。")
    if market_state in {"high_flyer_retreat", "risk_release", "panic"}:
        flags.append("市场处于退潮或风险释放阶段，主力结构买点阻断。")
    if sector_strength and sector_strength < 0.35:
        flags.append("板块强度不足，主力拉升共振不足。")
    if amount_ratio_1d_20d >= 2.8 and upper_shadow_ratio >= 0.35 and close < latest["open_price"]:
        flags.append("高位放量长上影，疑似出货风险。")
    if close < ma20 * 0.96:
        flags.append("跌破 20 日线过多，洗盘结构失效。")
    if latest["amount"] < 50_000_000:
        flags.append("成交额不足，流动性不支持主力买点。")
    return flags


def _mean(values: list[float]) -> float:
    values = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return sum(values) / len(values) if values else 0.0


def _stdev(values: list[float]) -> float:
    values = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if len(values) < 2:
        return 0.0
    avg = _mean(values)
    return math.sqrt(sum((value - avg) ** 2 for value in values) / len(values))


def _ratio(value: float, base: float) -> float:
    return float(value) / float(base) if base else 0.0


def _pct(high: float, low: float) -> float:
    return (float(high) / float(low) - 1.0) * 100.0 if low else 0.0


def _position(value: float, low: float, high: float) -> float:
    return (value - low) / (high - low) if high > low else 0.5


def _drawdown_pct(values: list[float]) -> float:
    if not values:
        return 0.0
    return (min(values) / max(values) - 1.0) * 100.0 if max(values) else 0.0


def _float(value: Any) -> float:
    try:
        numeric = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return numeric if math.isfinite(numeric) else 0.0
