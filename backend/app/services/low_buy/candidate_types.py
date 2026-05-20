from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import LowBuyHardRiskOut


@dataclass(frozen=True)
class CandidateMetrics:
    latest_trade_date: str
    retracement_days: int
    latest_open: float
    latest_close: float
    latest_high: float
    latest_low: float
    latest_change_pct: float
    ma5: float
    ma10: float
    ma20: float
    ma60: float
    board_open: float
    board_close: float
    board_low: float
    board_high: float
    board_mid_price: float
    board_gain_ok: bool
    volume_burst_ratio: float
    latest_volume_ratio: float
    post_volume_ratio: float
    shrink_staircase: bool
    close_to_ma5: float
    close_to_ma10: float
    close_to_ma20: float
    support_distance_pct: float
    support_distance_ma20_pct: float
    breakout_level: float
    breakout_distance_pct: float
    platform_high: float
    platform_low: float
    platform_window_days: int
    platform_range_pct: float
    platform_breakout_pct: float
    platform_support_distance_pct: float
    divergence_high: float
    divergence_volume_ratio: float
    divergence_day_stall: bool
    consolidation_days: int
    consolidation_low: float
    consolidation_high: float
    consolidation_volume_ratio: float
    consensus_breakout: bool
    consensus_volume_ratio: float
    consensus_close_strength: float
    recent_low_guard: float
    recent_swing_high: float
    drawdown_from_board_pct: float
    latest_body_pct: float
    upper_shadow_ratio: float
    lower_shadow_ratio: float
    close_position_ratio: float
    doji_like: bool
    long_lower_shadow: bool
    long_upper_shadow: bool
    weak_close: bool
    false_breakout_flag: bool
    stall_after_volume_flag: bool
    intraday_reversal_flag: bool
    distribution_risk_score: float
    momentum_exhaustion: bool
    trend_ok: bool
    strong_trend: bool
    support_ok: bool
    shrink_ok: bool
    shrink_basic_ok: bool
    board_low_held: bool
    board_open_held: bool
    support_watch_ok: bool
    latest_change_ok: bool
    trend_fatigue_score: float = 0.0
    shrink_quality_score: float = 0.0
    shrink_volatility: float = 0.0
    abnormal_volume_days: int = 0
    unfilled_gap_count: int = 0
    max_gap_size_pct: float = 0.0
    latest_gap_distance_pct: float = 0.0
    retracement_atr: float = 0.0
    retracement_atr_trend: float = 0.0
    atr14: float = 0.0
    atr_window: int = 14
    atr_source: str = "daily_ohlcv_true_range_14"
    drawdown_per_day: float = 0.0
    consecutive_lower_lows: int = 0
    support_touch_count: int = 0
    retracement_smoothness: float = 0.0
    multi_timeframe_resonance_score: float = 0.0
    multi_timeframe_resonance_text: str = ""


@dataclass(frozen=True)
class StrategySetup:
    entry_zone_low: float
    entry_zone_high: float
    execution_ready: bool
    execution_note: str
    summary_reason: str
    reasons: list[str]


@dataclass(frozen=True)
class CandidateContextAdjustment:
    score_penalty: float
    score_floor_shift: float
    soft_buy_threshold_shift: float
    candidate_penalty_weight: float
    market_position_multiplier: float
    risk_position_multiplier: float
    dynamic_position_multiplier: float
    industry_tier: str
    industry_tier_text: str
    industry_position_multiplier: float
    execution_blocked: bool
    risk_tier: str
    dynamic_adjustment_reason: str
    market_state: str
    market_state_text: str
    market_state_strength: float
    hard_risk: LowBuyHardRiskOut
    extra_risks: list[str]
    extra_tags: list[str]
