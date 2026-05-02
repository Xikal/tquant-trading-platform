from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import MicrostructureSnapshot, QuoteSnapshot, SectorSnapshot
from app.services.market.regime import MarketRegimeSnapshot
from app.services.quant_engine_models import IndicatorSnapshot


@dataclass(frozen=True)
class TradeScene:
    key: str
    label: str
    allowed_actions: set[str]
    reason: str


def resolve_trade_scene(
    *,
    quote: QuoteSnapshot,
    indicators: IndicatorSnapshot,
    sector: SectorSnapshot,
    microstructure: MicrostructureSnapshot,
    market_regime: MarketRegimeSnapshot | None,
) -> TradeScene:
    state = market_regime.state if market_regime is not None else "low_volume_wait"
    distribution = indicators.distribution
    if state == "risk_release" and quote.instrument_type != "etf":
        return _scene(
            "risk_release_hold",
            "风险释放观望",
            {"hold"},
            "市场处于风险释放期，个股做T先以保护本金为主。",
        )
    if distribution.false_breakout_flag or distribution.distribution_risk_score >= 7.2:
        return _scene(
            "distribution_defense",
            "派发防守",
            {"negative_t", "hold"},
            "出现假突破/派发风险，优先防守或反T。",
        )
    if indicators.intraday_structure == "pullback_acceptance":
        return _scene("pullback_acceptance", "回踩承接正T", {"positive_t", "hold"}, indicators.intraday_structure_text)
    if indicators.intraday_structure in {"overheat_exhaustion", "volume_stall", "false_breakout"}:
        return _scene("exhaustion_sell", "冲高衰竭反T", {"negative_t", "hold"}, indicators.intraday_structure_text)
    if _overheat_reversal_setup(quote, indicators, sector, microstructure):
        return _scene("overheat_reversal", "冲高回落反T", {"negative_t", "hold"}, "价格偏热且抛压增强，先评估反T。")
    if _trend_repair_setup(quote, indicators, sector, microstructure, state):
        return _scene("trend_repair", "趋势承接正T", {"positive_t", "hold"}, "趋势结构未坏且承接转强，优先评估正T。")
    if state in {"weight_support", "fast_rotation", "high_flyer_retreat"} and quote.instrument_type != "etf":
        return _scene(
            "defensive_rotation",
            "弱扩散防守",
            {"negative_t", "hold"},
            "市场扩散弱或轮动快，题材股先降进攻优先级。",
        )
    return _scene(
        "balanced_intraday",
        "均衡盘中",
        {"positive_t", "negative_t", "hold"},
        "没有明显单边场景，按分数和风控共同决定。",
    )


def _scene(key: str, label: str, allowed_actions: set[str], reason: str) -> TradeScene:
    return TradeScene(key=key, label=label, allowed_actions=allowed_actions, reason=reason)


def _overheat_reversal_setup(
    quote: QuoteSnapshot,
    indicators: IndicatorSnapshot,
    sector: SectorSnapshot,
    microstructure: MicrostructureSnapshot,
) -> bool:
    price_hot = quote.last_price >= max(indicators.ma5 * 1.008, indicators.vwap_value * 1.006)
    pressure_hot = indicators.rsi14 >= 66 or indicators.amplitude >= 3.0
    sell_pressure = microstructure.available and microstructure.sell_pressure >= 52
    weak_sector = sector.alignment_score <= 52
    return price_hot and pressure_hot and (sell_pressure or weak_sector)


def _trend_repair_setup(
    quote: QuoteSnapshot,
    indicators: IndicatorSnapshot,
    sector: SectorSnapshot,
    microstructure: MicrostructureSnapshot,
    market_state: str,
) -> bool:
    trend_ok = quote.last_price >= indicators.ma20 * 0.995 and indicators.ma5 >= indicators.ma20 * 0.998
    near_vwap = quote.last_price >= indicators.vwap_value * 0.993
    buy_pressure = not microstructure.available or microstructure.buy_pressure >= 48
    market_ok = market_state not in {"risk_release", "high_flyer_retreat"}
    return trend_ok and near_vwap and buy_pressure and sector.alignment_score >= 45 and market_ok
