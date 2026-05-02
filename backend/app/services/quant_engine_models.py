from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import KlineBar
from app.services.distribution_signals import DistributionSnapshot


@dataclass(frozen=True)
class IndicatorSnapshot:
    ma5: float
    ma20: float
    ma60: float
    rsi14: float
    macd_dif: float
    macd_dea: float
    macd_hist: float
    vwap_value: float
    atr14: float
    volume_ratio_value: float
    amplitude: float
    slope10: float
    obv_value: float
    distribution: DistributionSnapshot
    latest_bar: KlineBar | None
    intraday_structure: str = "unknown"
    intraday_structure_text: str = "分时结构不足"


@dataclass(frozen=True)
class ScoreSnapshot:
    tradability_score: float
    event_penalty: float
    scenario: str
    market_state: str
    market_state_text: str
    market_bonus: float
    positive_score: float
    negative_score: float
    signal_score: float
    risk_score: float
    risk_level: str
    positive_threshold: float
    negative_threshold: float


@dataclass(frozen=True)
class TradePlan:
    action: str
    entry_price: float | None
    exit_price: float | None
    stop_loss: float | None
    take_profit: float | None
    position_pct: float
    expected_profit_pct: float
    expected_loss_pct: float
    risk_reward_ratio: float
    slippage_bps: float
    min_profit_pct: float
    min_risk_reward_ratio: float
    trade_scene: str = ""
    trade_scene_text: str = ""
    buyback_trigger: str = ""
