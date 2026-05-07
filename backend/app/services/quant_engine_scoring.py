from __future__ import annotations

from app.models.schemas import MarketEventOut, MicrostructureSnapshot, QuoteSnapshot, SectorSnapshot
from app.services.distribution_signals import DistributionSnapshot
from app.services.market.regime import MarketRegimeSnapshot
from app.services.quant_engine_market import (
    market_state_description,
    market_state_text,
    market_threshold_shift,
)
from app.services.quant.runtime_parameters import get_position_t_scoring

QUANT_ENGINE_SCORING_VERSION = "quant-scoring-v1"
_DEFAULT_SCORING = {
    "version": QUANT_ENGINE_SCORING_VERSION,
    "base_scores": {"positive": 35.0, "negative": 30.0, "risk": 25.0},
    "action_thresholds": {
        "positive": 60.0,
        "negative": 62.0,
        "scenario_shifts": {
            "open_price_discovery": 5.0,
            "midday_consolidation": 2.0,
            "closing_repricing": 1.0,
        },
        "risk_level_shifts": {"high": 4.0, "low": -2.0},
    },
    "risk_level_thresholds": {"high": 65.0, "medium": 38.0},
    "positive_score": {
        "ma5_support": 10.0,
        "ma5_above_ma20": 8.0,
        "ma20_above_ma60": 6.0,
        "rsi_low": 44.0,
        "rsi_high": 62.0,
        "rsi_band_bonus": 10.0,
        "macd_non_negative_bonus": 8.0,
        "vwap_support_distance_pct": 0.006,
        "vwap_support_bonus": 12.0,
        "sector_alignment_threshold": 52.0,
        "sector_alignment_bonus": 5.0,
        "buy_pressure_threshold": 52.0,
        "buy_pressure_bonus": 4.0,
        "slope10_min": -0.3,
        "slope10_bonus": 5.0,
        "false_breakout_penalty": 10.0,
        "intraday_reversal_penalty": 6.0,
        "stall_after_volume_penalty": 4.0,
        "distribution_risk_weight": 0.45,
        "distribution_risk_cap": 4.5,
    },
    "negative_score": {
        "ma5_distance_multiplier": 1.005,
        "ma5_distance_bonus": 8.0,
        "high_rsi_threshold": 68.0,
        "high_rsi_bonus": 12.0,
        "macd_negative_bonus": 8.0,
        "vwap_distance_multiplier": 1.008,
        "vwap_distance_bonus": 12.0,
        "high_amplitude_threshold": 3.0,
        "high_amplitude_bonus": 8.0,
        "sector_alignment_threshold": 54.0,
        "sector_weak_bonus": 5.0,
        "sell_pressure_threshold": 52.0,
        "sell_pressure_bonus": 5.0,
        "false_breakout_bonus": 8.0,
        "intraday_reversal_bonus": 5.5,
        "stall_after_volume_bonus": 4.0,
        "distribution_risk_weight": 0.35,
        "distribution_risk_cap": 3.5,
    },
    "risk_score": {
        "amplitude_floor": 5.0,
        "amplitude_weight": 4.0,
        "atr_weight": 3.0,
        "tradability_floor": 55.0,
        "tradability_weight": 0.6,
        "sector_alignment_floor": 50.0,
        "sector_alignment_weight": 0.25,
        "event_medium_penalty": 6.0,
        "event_high_penalty": 15.0,
    },
}


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
