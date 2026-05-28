from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any

from app.models.schemas import KlineBar
from app.services.etf.universe import EtfProfile, etf_profile_for
from app.services.indicators import bollinger_bands, rsi_wilder, trend_slope, volume_ratio, vwap
from app.services.market.parameter_defaults import MARKET_SECTOR_ETF_T0_DEFAULTS


ETF_T0_SIGNAL_VERSION = "etf-t0-signal-v1"


@dataclass(frozen=True)
class EtfT0SignalParams:
    min_bars: int = 20
    bollinger_window: int = 20
    bollinger_std: float = 2.0
    rsi_period: int = 14
    buy_vwap_deviation_pct: float = 0.35
    sell_vwap_deviation_pct: float = 0.35
    min_net_edge_pct: float = 0.12
    oversold_rsi: float = 38.0
    overbought_rsi: float = 64.0
    max_volume_ratio: float = 3.5
    min_volume_ratio: float = 0.2
    max_trend_slope_abs_pct: float = 1.6
    stop_loss_pct: float = -0.45
    target_buffer_pct: float = 0.05
    liquidity_intraday_amount_ratio: float = 0.02
    tracking_divergence_block_pct: float = 1.6


@dataclass(frozen=True)
class EtfT0Signal:
    symbol: str
    name: str
    action: str = "hold"
    action_text: str = "只观察"
    confidence: float = 0.0
    data_quality: str = "unavailable"
    data_quality_text: str = "分钟数据不可用"
    t0_eligible: bool = False
    settlement_rule: str = "t1"
    etf_category: str = "unknown"
    current_price: float = 0.0
    vwap: float = 0.0
    vwap_deviation_pct: float = 0.0
    rsi: float = 50.0
    bollinger_upper: float = 0.0
    bollinger_middle: float = 0.0
    bollinger_lower: float = 0.0
    volume_ratio: float = 0.0
    trend_slope_pct: float = 0.0
    total_amount: float = 0.0
    spread_bps: float = 0.0
    tracking_index_change_pct: float | None = None
    tracking_divergence_pct: float | None = None
    expected_edge_pct: float = 0.0
    round_trip_cost_pct: float = 0.0
    target_price: float = 0.0
    stop_price: float = 0.0
    reasons: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    version: str = ETF_T0_SIGNAL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "action": self.action,
            "action_text": self.action_text,
            "confidence": self.confidence,
            "data_quality": self.data_quality,
            "data_quality_text": self.data_quality_text,
            "t0_eligible": self.t0_eligible,
            "settlement_rule": self.settlement_rule,
            "etf_category": self.etf_category,
            "current_price": self.current_price,
            "vwap": self.vwap,
            "vwap_deviation_pct": self.vwap_deviation_pct,
            "rsi": self.rsi,
            "bollinger_upper": self.bollinger_upper,
            "bollinger_middle": self.bollinger_middle,
            "bollinger_lower": self.bollinger_lower,
            "volume_ratio": self.volume_ratio,
            "trend_slope_pct": self.trend_slope_pct,
            "total_amount": self.total_amount,
            "spread_bps": self.spread_bps,
            "tracking_index_change_pct": self.tracking_index_change_pct,
            "tracking_divergence_pct": self.tracking_divergence_pct,
            "expected_edge_pct": self.expected_edge_pct,
            "round_trip_cost_pct": self.round_trip_cost_pct,
            "target_price": self.target_price,
            "stop_price": self.stop_price,
            "reasons": list(self.reasons),
            "risk_flags": list(self.risk_flags),
            "version": self.version,
        }


def evaluate_etf_t0_signal(
    *,
    symbol: str,
    name: str = "",
    bars: list[KlineBar],
    spread_bps: float | None = None,
    tracking_index_change_pct: float | None = None,
    data_quality: str = "fresh",
    params: dict[str, Any] | EtfT0SignalParams | None = None,
) -> EtfT0Signal:
    resolved_params = _resolve_params(params)
    profile = etf_profile_for(symbol, name=name, instrument_type="fund")
    profile_name = name or (profile.name if profile is not None else symbol)
    if profile is None:
        return _blocked(
            symbol=symbol,
            name=profile_name,
            profile=None,
            data_quality="unavailable",
            data_quality_text="不是 ETF universe 中可识别的 ETF。",
            risk_flags=["not_etf"],
        )
    if not profile.same_day_sell_allowed:
        return _blocked(
            symbol=profile.symbol,
            name=profile_name,
            profile=profile,
            data_quality="fresh",
            data_quality_text="ETF universe 未放行 T+0，只允许观察或 T+1 处理。",
            risk_flags=["t0_not_allowed"],
        )
    if str(data_quality or "").lower() in {"stale", "unavailable", "bad"}:
        return _blocked(
            symbol=profile.symbol,
            name=profile_name,
            profile=profile,
            data_quality=str(data_quality or "stale"),
            data_quality_text="行情数据 stale 或不可用，禁止生成 ETF 做T信号。",
            risk_flags=["stale_data"],
        )
    clean_bars = _clean_bars(bars)
    if len(clean_bars) < resolved_params.min_bars:
        return _blocked(
            symbol=profile.symbol,
            name=profile_name,
            profile=profile,
            data_quality="partial",
            data_quality_text=f"分钟样本不足 {resolved_params.min_bars} 根，当前 {len(clean_bars)} 根。",
            risk_flags=["insufficient_bars"],
        )

    close_values = [float(bar.close) for bar in clean_bars]
    current_price = close_values[-1]
    vwap_value = vwap(clean_bars)
    if current_price <= 0 or vwap_value <= 0:
        return _blocked(
            symbol=profile.symbol,
            name=profile_name,
            profile=profile,
            data_quality="partial",
            data_quality_text="分钟价格或 VWAP 不可用。",
            risk_flags=["invalid_price"],
        )

    upper, middle, lower = bollinger_bands(
        close_values,
        window=resolved_params.bollinger_window,
        num_std=resolved_params.bollinger_std,
    )
    rsi_value = rsi_wilder(close_values, resolved_params.rsi_period)
    volume_ratio_value = volume_ratio(clean_bars, lookback=resolved_params.bollinger_window)
    slope_value = trend_slope(close_values, window=min(10, max(2, len(close_values) - 1)))
    total_amount = _total_amount(clean_bars)
    spread_value = _safe_float(spread_bps)
    vwap_deviation = (current_price / vwap_value - 1.0) * 100
    tracking_divergence = _tracking_divergence(close_values, tracking_index_change_pct)
    round_trip_cost = _round_trip_cost_pct(profile=profile, spread_bps=spread_value)
    expected_edge = abs(vwap_deviation) - round_trip_cost

    risk_flags = _risk_flags(
        profile=profile,
        params=resolved_params,
        spread_bps=spread_value,
        total_amount=total_amount,
        volume_ratio_value=volume_ratio_value,
        slope_value=slope_value,
        tracking_divergence=tracking_divergence,
    )
    reasons = [
        f"VWAP偏离 {vwap_deviation:.2f}%",
        f"RSI {rsi_value:.1f}",
        f"量比 {volume_ratio_value:.2f}",
    ]
    if risk_flags:
        return EtfT0Signal(
            symbol=profile.symbol,
            name=profile_name,
            action="hold",
            action_text="风险阻断",
            confidence=0.0,
            data_quality="partial",
            data_quality_text="; ".join(_risk_text(flag) for flag in risk_flags),
            t0_eligible=True,
            settlement_rule=profile.settlement_rule,
            etf_category=profile.category.value,
            current_price=round(current_price, 4),
            vwap=round(vwap_value, 4),
            vwap_deviation_pct=round(vwap_deviation, 4),
            rsi=round(rsi_value, 4),
            bollinger_upper=upper,
            bollinger_middle=middle,
            bollinger_lower=lower,
            volume_ratio=round(volume_ratio_value, 4),
            trend_slope_pct=round(slope_value, 4),
            total_amount=round(total_amount, 2),
            spread_bps=round(spread_value, 4),
            tracking_index_change_pct=tracking_index_change_pct,
            tracking_divergence_pct=tracking_divergence,
            expected_edge_pct=round(expected_edge, 4),
            round_trip_cost_pct=round(round_trip_cost, 4),
            reasons=reasons,
            risk_flags=risk_flags,
        )

    if expected_edge < resolved_params.min_net_edge_pct:
        return EtfT0Signal(
            symbol=profile.symbol,
            name=profile_name,
            action="hold",
            action_text="价差不足",
            confidence=25.0,
            data_quality="fresh",
            data_quality_text="VWAP 偏离扣除估算价差/滑点后不足以覆盖最小净边际。",
            t0_eligible=True,
            settlement_rule=profile.settlement_rule,
            etf_category=profile.category.value,
            current_price=round(current_price, 4),
            vwap=round(vwap_value, 4),
            vwap_deviation_pct=round(vwap_deviation, 4),
            rsi=round(rsi_value, 4),
            bollinger_upper=upper,
            bollinger_middle=middle,
            bollinger_lower=lower,
            volume_ratio=round(volume_ratio_value, 4),
            trend_slope_pct=round(slope_value, 4),
            total_amount=round(total_amount, 2),
            spread_bps=round(spread_value, 4),
            tracking_index_change_pct=tracking_index_change_pct,
            tracking_divergence_pct=tracking_divergence,
            expected_edge_pct=round(expected_edge, 4),
            round_trip_cost_pct=round(round_trip_cost, 4),
            reasons=reasons,
            risk_flags=["edge_too_small"],
        )

    action, action_text, confidence = _classify_action(
        close_values=close_values,
        current_price=current_price,
        lower=lower,
        upper=upper,
        vwap_deviation=vwap_deviation,
        rsi_value=rsi_value,
        volume_ratio_value=volume_ratio_value,
        params=resolved_params,
    )
    target_price, stop_price = _prices_for_action(
        action=action,
        current_price=current_price,
        vwap_value=vwap_value,
        params=resolved_params,
    )
    if action == "hold":
        reasons.append("未同时满足 VWAP 偏离、布林带、RSI 和回归确认。")
    elif action == "positive_t_buy":
        reasons.append("价格低于 VWAP/布林下轨且 RSI 低位修复，正T先买后卖候选。")
    elif action == "negative_t_sell":
        reasons.append("价格高于 VWAP/布林上轨且 RSI 偏热，反T先卖后买候选。")

    return EtfT0Signal(
        symbol=profile.symbol,
        name=profile_name,
        action=action,
        action_text=action_text,
        confidence=round(confidence, 2),
        data_quality="fresh",
        data_quality_text="ETF 分钟信号已计算；执行前仍需订单、持仓和风控校验。",
        t0_eligible=True,
        settlement_rule=profile.settlement_rule,
        etf_category=profile.category.value,
        current_price=round(current_price, 4),
        vwap=round(vwap_value, 4),
        vwap_deviation_pct=round(vwap_deviation, 4),
        rsi=round(rsi_value, 4),
        bollinger_upper=upper,
        bollinger_middle=middle,
        bollinger_lower=lower,
        volume_ratio=round(volume_ratio_value, 4),
        trend_slope_pct=round(slope_value, 4),
        total_amount=round(total_amount, 2),
        spread_bps=round(spread_value, 4),
        tracking_index_change_pct=tracking_index_change_pct,
        tracking_divergence_pct=tracking_divergence,
        expected_edge_pct=round(expected_edge, 4),
        round_trip_cost_pct=round(round_trip_cost, 4),
        target_price=round(target_price, 4),
        stop_price=round(stop_price, 4),
        reasons=reasons,
        risk_flags=[] if action != "hold" else ["no_setup"],
    )


def _resolve_params(params: dict[str, Any] | EtfT0SignalParams | None) -> EtfT0SignalParams:
    if isinstance(params, EtfT0SignalParams):
        return params
    values = dict(MARKET_SECTOR_ETF_T0_DEFAULTS)
    if isinstance(params, dict):
        values.update(params)
    return EtfT0SignalParams(
        min_bars=_int_value(values.get("signal_min_bars"), 20),
        bollinger_window=_int_value(values.get("signal_bollinger_window"), 20),
        bollinger_std=_float_value(values.get("signal_bollinger_std"), 2.0),
        rsi_period=_int_value(values.get("signal_rsi_period"), 14),
        buy_vwap_deviation_pct=_float_value(values.get("signal_buy_vwap_deviation_pct"), 0.35),
        sell_vwap_deviation_pct=_float_value(values.get("signal_sell_vwap_deviation_pct"), 0.35),
        min_net_edge_pct=_float_value(values.get("signal_min_net_edge_pct"), 0.12),
        oversold_rsi=_float_value(values.get("signal_oversold_rsi"), 38.0),
        overbought_rsi=_float_value(values.get("signal_overbought_rsi"), 64.0),
        max_volume_ratio=_float_value(values.get("signal_max_volume_ratio"), 3.5),
        min_volume_ratio=_float_value(values.get("signal_min_volume_ratio"), 0.2),
        max_trend_slope_abs_pct=_float_value(values.get("signal_max_trend_slope_abs_pct"), 1.6),
        stop_loss_pct=_float_value(values.get("signal_stop_loss_pct"), -0.45),
        target_buffer_pct=_float_value(values.get("signal_target_buffer_pct"), 0.05),
        liquidity_intraday_amount_ratio=_float_value(values.get("signal_liquidity_intraday_amount_ratio"), 0.02),
        tracking_divergence_block_pct=_float_value(values.get("signal_tracking_divergence_block_pct"), 1.6),
    )


def _classify_action(
    *,
    close_values: list[float],
    current_price: float,
    lower: float,
    upper: float,
    vwap_deviation: float,
    rsi_value: float,
    volume_ratio_value: float,
    params: EtfT0SignalParams,
) -> tuple[str, str, float]:
    reclaiming = _is_reclaiming(close_values)
    rolling_over = _is_rolling_over(close_values)
    positive_score = 0.0
    if vwap_deviation <= -params.buy_vwap_deviation_pct:
        positive_score += 28.0
    if current_price <= lower * 1.003:
        positive_score += 22.0
    if rsi_value <= params.oversold_rsi:
        positive_score += 20.0
    if reclaiming:
        positive_score += 18.0
    if params.min_volume_ratio <= volume_ratio_value <= 1.6:
        positive_score += 8.0
    if positive_score >= 62.0:
        return "positive_t_buy", "ETF 正T买入候选", min(95.0, positive_score)

    negative_score = 0.0
    if vwap_deviation >= params.sell_vwap_deviation_pct:
        negative_score += 28.0
    if current_price >= upper * 0.997:
        negative_score += 22.0
    if rsi_value >= params.overbought_rsi:
        negative_score += 20.0
    if rolling_over:
        negative_score += 18.0
    if params.min_volume_ratio <= volume_ratio_value <= params.max_volume_ratio:
        negative_score += 8.0
    if negative_score >= 62.0:
        return "negative_t_sell", "ETF 反T卖出候选", min(95.0, negative_score)
    return "hold", "只观察", max(20.0, min(60.0, positive_score, negative_score))


def _risk_flags(
    *,
    profile: EtfProfile,
    params: EtfT0SignalParams,
    spread_bps: float,
    total_amount: float,
    volume_ratio_value: float,
    slope_value: float,
    tracking_divergence: float | None,
) -> list[str]:
    flags: list[str] = []
    if spread_bps > 0 and profile.max_spread_bps > 0 and spread_bps > profile.max_spread_bps:
        flags.append("spread_too_wide")
    min_intraday_amount = float(profile.min_amount or 0.0) * params.liquidity_intraday_amount_ratio
    if min_intraday_amount > 0 and total_amount > 0 and total_amount < min_intraday_amount:
        flags.append("liquidity_too_low")
    if volume_ratio_value > params.max_volume_ratio:
        flags.append("volume_spike")
    if volume_ratio_value > 0 and volume_ratio_value < params.min_volume_ratio:
        flags.append("volume_too_thin")
    if abs(slope_value) > params.max_trend_slope_abs_pct:
        flags.append("one_way_trend")
    if tracking_divergence is not None and abs(tracking_divergence) > params.tracking_divergence_block_pct:
        flags.append("tracking_divergence")
    return flags


def _blocked(
    *,
    symbol: str,
    name: str,
    profile: EtfProfile | None,
    data_quality: str,
    data_quality_text: str,
    risk_flags: list[str],
) -> EtfT0Signal:
    return EtfT0Signal(
        symbol=symbol,
        name=name,
        action="hold",
        action_text="不可执行",
        confidence=0.0,
        data_quality=data_quality,
        data_quality_text=data_quality_text,
        t0_eligible=bool(profile and profile.same_day_sell_allowed),
        settlement_rule=profile.settlement_rule if profile is not None else "t1",
        etf_category=profile.category.value if profile is not None else "unknown",
        risk_flags=risk_flags,
    )


def _clean_bars(bars: list[KlineBar]) -> list[KlineBar]:
    valid = [
        bar
        for bar in bars
        if _is_positive_number(getattr(bar, "close", 0))
        and _is_positive_number(getattr(bar, "high", 0))
        and _is_positive_number(getattr(bar, "low", 0))
    ]
    return sorted(valid, key=lambda item: str(getattr(item, "timestamp", "") or ""))


def _total_amount(bars: list[KlineBar]) -> float:
    total = sum(_safe_float(getattr(bar, "amount", 0)) for bar in bars)
    if total > 0:
        return total
    return sum(_safe_float(getattr(bar, "close", 0)) * _safe_float(getattr(bar, "volume", 0)) for bar in bars)


def _tracking_divergence(close_values: list[float], tracking_index_change_pct: float | None) -> float | None:
    if tracking_index_change_pct is None or not close_values:
        return None
    first = close_values[0]
    if first <= 0:
        return None
    etf_change = (close_values[-1] / first - 1.0) * 100
    return round(etf_change - float(tracking_index_change_pct), 4)


def _round_trip_cost_pct(*, profile: EtfProfile, spread_bps: float) -> float:
    slippage_bps = max(float(profile.slippage_bps or 0.0), 0.0) * 2
    spread_cost_bps = max(spread_bps, 0.0)
    return (slippage_bps + spread_cost_bps) / 100.0


def _prices_for_action(
    *,
    action: str,
    current_price: float,
    vwap_value: float,
    params: EtfT0SignalParams,
) -> tuple[float, float]:
    if action == "positive_t_buy":
        target = max(vwap_value * (1 - params.target_buffer_pct / 100), current_price)
        stop = current_price * (1 + params.stop_loss_pct / 100)
        return target, stop
    if action == "negative_t_sell":
        target = min(vwap_value * (1 + params.target_buffer_pct / 100), current_price)
        stop = current_price * (1 - params.stop_loss_pct / 100)
        return target, stop
    return 0.0, 0.0


def _is_reclaiming(values: list[float]) -> bool:
    return len(values) >= 3 and values[-1] > values[-2] >= values[-3]


def _is_rolling_over(values: list[float]) -> bool:
    return len(values) >= 3 and values[-1] < values[-2] <= values[-3]


def _risk_text(flag: str) -> str:
    return {
        "spread_too_wide": "盘口价差过大",
        "liquidity_too_low": "分钟成交额低于流动性门槛",
        "volume_spike": "分钟量能异常放大",
        "volume_too_thin": "分钟量能过薄",
        "one_way_trend": "分时单边趋势过强",
        "tracking_divergence": "ETF 与跟踪指数背离过大",
    }.get(flag, flag)


def _safe_float(value: Any) -> float:
    try:
        result = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return result if isfinite(result) else 0.0


def _float_value(value: Any, fallback: float) -> float:
    result = _safe_float(value)
    return result if result != 0.0 else fallback


def _int_value(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _is_positive_number(value: Any) -> bool:
    return _safe_float(value) > 0
