from __future__ import annotations

from app.models.schemas import MarketEventOut, MicrostructureSnapshot, QuoteSnapshot, SectorSnapshot
from app.services.distribution_signals import DistributionSnapshot
from app.services.market.regime import MarketRegimeSnapshot
from app.services.quant_engine_market import (
    market_state_description,
    market_state_text,
    market_threshold_shift,
)

QUANT_ENGINE_SCORING_VERSION = "quant-scoring-v1"
POSITIVE_BASE_SCORE = 35.0
NEGATIVE_BASE_SCORE = 30.0
RISK_BASE_SCORE = 25.0
DEFAULT_POSITIVE_THRESHOLD = 60.0
DEFAULT_NEGATIVE_THRESHOLD = 62.0
RISK_LEVEL_HIGH_THRESHOLD = 65.0
RISK_LEVEL_MEDIUM_THRESHOLD = 38.0
VWAP_SUPPORT_DISTANCE_PCT = 0.006
NEGATIVE_MA5_DISTANCE_MULTIPLIER = 1.005
NEGATIVE_VWAP_DISTANCE_MULTIPLIER = 1.008
HIGH_RSI_THRESHOLD = 68.0
HIGH_AMPLITUDE_THRESHOLD = 3.0


def action_thresholds(
    scenario: str,
    risk_level: str,
    market_regime: MarketRegimeSnapshot | None = None,
) -> tuple[float, float]:
    positive_threshold = DEFAULT_POSITIVE_THRESHOLD
    negative_threshold = DEFAULT_NEGATIVE_THRESHOLD
    if scenario == "open_price_discovery":
        positive_threshold += 5
        negative_threshold += 5
    elif scenario == "midday_consolidation":
        positive_threshold += 2
        negative_threshold += 2
    elif scenario == "closing_repricing":
        positive_threshold += 1
        negative_threshold += 1

    if risk_level == "high":
        positive_threshold += 4
        negative_threshold += 4
    elif risk_level == "low":
        positive_threshold -= 2
        negative_threshold -= 2
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
    score = POSITIVE_BASE_SCORE
    if quote.last_price >= ma5:
        score += 10
    if ma5 >= ma20:
        score += 8
    if ma20 >= ma60:
        score += 6
    if 44 <= rsi14 <= 62:
        score += 10
    if macd_hist >= 0:
        score += 8
    if abs(quote.last_price - vwap_value) / max(vwap_value, 0.01) <= VWAP_SUPPORT_DISTANCE_PCT:
        score += 12
    if sector.alignment_score >= 52:
        score += 5
    if microstructure.available and microstructure.buy_pressure >= 52:
        score += 4
    if slope10 > -0.3:
        score += 5
    if distribution.false_breakout_flag:
        score -= 10
    elif distribution.intraday_reversal_flag:
        score -= 6
    elif distribution.stall_after_volume_flag:
        score -= 4
    score -= min(distribution.distribution_risk_score * 0.45, 4.5)
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
    score = NEGATIVE_BASE_SCORE
    if quote.last_price >= ma5 * NEGATIVE_MA5_DISTANCE_MULTIPLIER:
        score += 8
    if rsi14 >= HIGH_RSI_THRESHOLD:
        score += 12
    if macd_hist < 0:
        score += 8
    if quote.last_price >= vwap_value * NEGATIVE_VWAP_DISTANCE_MULTIPLIER:
        score += 12
    if amplitude >= HIGH_AMPLITUDE_THRESHOLD:
        score += 8
    if sector.alignment_score <= 54:
        score += 5
    if microstructure.available and microstructure.sell_pressure >= 52:
        score += 5
    if distribution.false_breakout_flag:
        score += 8
    elif distribution.intraday_reversal_flag:
        score += 5.5
    elif distribution.stall_after_volume_flag:
        score += 4
    score += min(distribution.distribution_risk_score * 0.35, 3.5)
    return max(0.0, min(100.0, score))


def risk_score(
    amplitude: float,
    atr_value: float,
    tradability_score: float,
    sector: SectorSnapshot,
    events: list[MarketEventOut],
) -> float:
    score = RISK_BASE_SCORE
    score += max(0.0, amplitude - 5.0) * 4
    score += atr_value * 3
    score += max(0.0, 55 - tradability_score) * 0.6
    score += max(0.0, 50 - sector.alignment_score) * 0.25
    for event in events:
        if event.risk_level == "medium":
            score += 6
        elif event.risk_level == "high":
            score += 15
    return max(0.0, min(100.0, score))


def risk_level(score: float) -> str:
    if score >= RISK_LEVEL_HIGH_THRESHOLD:
        return "high"
    if score >= RISK_LEVEL_MEDIUM_THRESHOLD:
        return "medium"
    return "low"


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
