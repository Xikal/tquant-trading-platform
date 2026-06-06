from __future__ import annotations

from dataclasses import dataclass, field

from app.models.schemas import LowBuyCandidateOut, LowBuyStrategyPerformanceOut


@dataclass
class StrategyHit:
    strategy_key: str
    strategy_title: str
    family_key: str
    candidate: LowBuyCandidateOut
    strategy_weight_score: float
    context_bonus: float
    performance: LowBuyStrategyPerformanceOut | None = None


@dataclass
class PriorityCandidate:
    symbol: str
    hits: list[StrategyHit] = field(default_factory=list)


@dataclass
class PriorityMarketContext:
    market_state: str
    market_bonus: float
    market_state_strength: float
    regime_confidence: float
    state_persistence_days: int
    transition_risk: float
    market_state_label: str
    market_state_description: str
    breadth_ready: bool
    emotion_ready: bool
    stock_up_ratio: float
    stock_median_change: float
    style_divergence: float
    hot_turnover: float
    hot_overlap_ratio: float
    limit_down_count: int | None
    limit_up_count: int
    board_height: int
    previous_board_height: int
    promotion_ratio: float
    broken_board_ratio: float
    promotion_break_gap: float
    promotion_break_pressure: float
    high_flyer_retreat_ratio: float
    high_flyer_gap_speed: float
    distribution_pressure: float
    emotion_temperature: str
    emotion_temperature_text: str
    emotion_temperature_score: float
    hot_industries: list[str]
    hot_industry_source: str
    hot_industry_source_text: str
    mainline_lifecycle_state: str
    mainline_lifecycle_text: str
    industry_ranks: dict[str, int]


@dataclass
class PriorityBaseSnapshot:
    latest_trade_date: str
    latest_available_trade_date: str
    updated_at: str
    candidates: list[PriorityCandidate]
    market_context: PriorityMarketContext
    expected_trade_date: str = ""
    staleness_trade_days: int = 0
    missing_strategies: list[str] = field(default_factory=list)
    stale_strategies: list[str] = field(default_factory=list)
