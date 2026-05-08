from __future__ import annotations

from app.models.schemas import MarketEventOut, MicrostructureSnapshot, QuoteSnapshot, SectorSnapshot
from app.services.distribution_signals import DistributionSnapshot
from app.services.market.regime import MarketRegimeSnapshot
from app.services.quant_engine_market import (
    market_state_description,
    market_state_text,
    market_threshold_shift,
)
from app.services.low_buy.strategy_parameter_defaults import POSITION_T_SCORING_DEFAULTS
from app.services.quant.runtime_parameters import get_position_t_scoring

QUANT_ENGINE_SCORING_VERSION = "quant-scoring-v1"
_DEFAULT_SCORING = POSITION_T_SCORING_DEFAULTS


def action_thresholds(
    scenario: str,
    risk_level: str,
    market_regime: MarketRegimeSnapshot | None = None,
) -> tuple[float, float]:
    params = _scoring_params()
    action_params = params["action_thresholds"]
    positive_threshold = float(action_params["positive"])
    negative_threshold = float(action_params["negative"])
    scenario_shifts = action_params.get("scenario_shifts", {})
    risk_level_shifts = action_params.get("risk_level_shifts", {})
    if scenario == "open_price_discovery":
        shift = float(scenario_shifts.get("open_price_discovery", 0.0))
        positive_threshold += shift
        negative_threshold += shift
    elif scenario == "midday_consolidation":
        shift = float(scenario_shifts.get("midday_consolidation", 0.0))
        positive_threshold += shift
        negative_threshold += shift
    elif scenario == "closing_repricing":
        shift = float(scenario_shifts.get("closing_repricing", 0.0))
        positive_threshold += shift
        negative_threshold += shift

    if risk_level == "high":
        shift = float(risk_level_shifts.get("high", 0.0))
        positive_threshold += shift
        negative_threshold += shift
    elif risk_level == "low":
        shift = float(risk_level_shifts.get("low", 0.0))
        positive_threshold += shift
        negative_threshold += shift
    positive_shift, negative_shift = market_threshold_shift(market_regime)
    positive_threshold += positive_shift
    negative_threshold += negative_shift
    return positive_threshold, negative_threshold


def positive_score(
    quote: QuoteSnapshot,
    ma5: float,
    ma20: float,
    ma60: float,
    rsi14: float,
    macd_hist: float,
    vwap_value: float,
    sector: SectorSnapshot,
    microstructure: MicrostructureSnapshot,
    slope10: float,
    distribution: DistributionSnapshot,
) -> float:
    params = _scoring_params()
    score_params = params["positive_score"]
    score = float(params["base_scores"]["positive"])
    if quote.last_price >= ma5:
        score += float(score_params["ma5_support"])
    if ma5 >= ma20:
        score += float(score_params["ma5_above_ma20"])
    if ma20 >= ma60:
        score += float(score_params["ma20_above_ma60"])
    if float(score_params["rsi_low"]) <= rsi14 <= float(score_params["rsi_high"]):
        score += float(score_params["rsi_band_bonus"])
    if macd_hist >= 0:
        score += float(score_params["macd_non_negative_bonus"])
    if abs(quote.last_price - vwap_value) / max(vwap_value, 0.01) <= float(score_params["vwap_support_distance_pct"]):
        score += float(score_params["vwap_support_bonus"])
    if sector.alignment_score >= float(score_params["sector_alignment_threshold"]):
        score += float(score_params["sector_alignment_bonus"])
    if microstructure.available and microstructure.buy_pressure >= float(score_params["buy_pressure_threshold"]):
        score += float(score_params["buy_pressure_bonus"])
    if slope10 > float(score_params["slope10_min"]):
        score += float(score_params["slope10_bonus"])
    if distribution.false_breakout_flag:
        score -= float(score_params["false_breakout_penalty"])
    elif distribution.intraday_reversal_flag:
        score -= float(score_params["intraday_reversal_penalty"])
    elif distribution.stall_after_volume_flag:
        score -= float(score_params["stall_after_volume_penalty"])
    score -= min(
        distribution.distribution_risk_score * float(score_params["distribution_risk_weight"]),
        float(score_params["distribution_risk_cap"]),
    )
    return max(0.0, min(100.0, score))


def negative_score(
    quote: QuoteSnapshot,
    ma5: float,
    rsi14: float,
    macd_hist: float,
    vwap_value: float,
    sector: SectorSnapshot,
    microstructure: MicrostructureSnapshot,
    amplitude: float,
    distribution: DistributionSnapshot,
) -> float:
    params = _scoring_params()
    score_params = params["negative_score"]
    score = float(params["base_scores"]["negative"])
    if quote.last_price >= ma5 * float(score_params["ma5_distance_multiplier"]):
        score += float(score_params["ma5_distance_bonus"])
    if rsi14 >= float(score_params["high_rsi_threshold"]):
        score += float(score_params["high_rsi_bonus"])
    if macd_hist < 0:
        score += float(score_params["macd_negative_bonus"])
    if quote.last_price >= vwap_value * float(score_params["vwap_distance_multiplier"]):
        score += float(score_params["vwap_distance_bonus"])
    if amplitude >= float(score_params["high_amplitude_threshold"]):
        score += float(score_params["high_amplitude_bonus"])
    if sector.alignment_score <= float(score_params["sector_alignment_threshold"]):
        score += float(score_params["sector_weak_bonus"])
    if microstructure.available and microstructure.sell_pressure >= float(score_params["sell_pressure_threshold"]):
        score += float(score_params["sell_pressure_bonus"])
    if distribution.false_breakout_flag:
        score += float(score_params["false_breakout_bonus"])
    elif distribution.intraday_reversal_flag:
        score += float(score_params["intraday_reversal_bonus"])
    elif distribution.stall_after_volume_flag:
        score += float(score_params["stall_after_volume_bonus"])
    score += min(
        distribution.distribution_risk_score * float(score_params["distribution_risk_weight"]),
        float(score_params["distribution_risk_cap"]),
    )
    return max(0.0, min(100.0, score))


def risk_score(
    amplitude: float,
    atr_value: float,
    tradability_score: float,
    sector: SectorSnapshot,
    events: list[MarketEventOut],
) -> float:
    params = _scoring_params()
    risk_params = params["risk_score"]
    score = float(params["base_scores"]["risk"])
    score += max(0.0, amplitude - float(risk_params["amplitude_floor"])) * float(risk_params["amplitude_weight"])
    score += atr_value * float(risk_params["atr_weight"])
    score += max(0.0, float(risk_params["tradability_floor"]) - tradability_score) * float(risk_params["tradability_weight"])
    score += max(0.0, float(risk_params["sector_alignment_floor"]) - sector.alignment_score) * float(risk_params["sector_alignment_weight"])
    for event in events:
        if event.risk_level == "medium":
            score += float(risk_params["event_medium_penalty"])
        elif event.risk_level == "high":
            score += float(risk_params["event_high_penalty"])
    return max(0.0, min(100.0, score))


def risk_level(score: float) -> str:
    thresholds = _scoring_params()["risk_level_thresholds"]
    if score >= float(thresholds["high"]):
        return "high"
    if score >= float(thresholds["medium"]):
        return "medium"
    return "low"


def _scoring_params() -> dict:
    return _deep_merge(_DEFAULT_SCORING, get_position_t_scoring())


def _deep_merge(defaults: dict, overrides: dict) -> dict:
    result = dict(defaults)
    for key, value in overrides.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def build_reasons(
    action: str,
    market_regime: MarketRegimeSnapshot | None,
    positive_score_value: float,
    negative_score_value: float,
    ma5: float,
    ma20: float,
    rsi14: float,
    macd_hist: float,
    vwap_value: float,
    sector: SectorSnapshot,
    microstructure: MicrostructureSnapshot,
    scenario: str,
    distribution: DistributionSnapshot,
) -> list[str]:
    reasons = [
        f"当前场景识别为 {scenario}。",
        f"市场状态为 {market_state_text(market_regime)}，{market_state_description(market_regime)}",
        f"MA5/MA20 分别为 {ma5:.2f}/{ma20:.2f}，RSI14 为 {rsi14:.2f}。",
        f"MACD 柱值 {macd_hist:.3f}，VWAP 为 {vwap_value:.2f}。",
        f"市场/板块联动评分 {sector.alignment_score:.1f}。",
    ]
    if microstructure.available:
        reasons.append(
            f"买卖压力约为 {microstructure.buy_pressure:.1f}/{microstructure.sell_pressure:.1f}。"
        )
    if distribution.false_breakout_flag:
        reasons.append("分时出现假突破回落，优先防范拉高出货。")
    elif distribution.intraday_reversal_flag:
        reasons.append("分时冲高回落明显，优先考虑减仓或反T。")
    elif distribution.stall_after_volume_flag:
        reasons.append("分时存在放量滞涨，继续追买的性价比下降。")
    if action == "positive_t":
        reasons.append(f"正T得分 {positive_score_value:.1f} 高于反T得分 {negative_score_value:.1f}。")
    elif action == "negative_t":
        reasons.append(f"反T得分 {negative_score_value:.1f} 高于正T得分 {positive_score_value:.1f}。")
    else:
        reasons.append("当前信号与风控条件未形成高质量做T共振，先观望。")
    return reasons
