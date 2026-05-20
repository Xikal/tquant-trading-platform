from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class MarketBreadthResponse(BaseModel):
    updated_at: str
    state: str = ""
    state_text: str = ""
    breadth_ready: bool = False
    emotion_ready: bool = False
    stock_up_ratio: float = 0.0
    stock_median_change: float = 0.0
    largecap_change: float = 0.0
    smallcap_change: float = 0.0
    style_divergence: float = 0.0
    limit_up_count: int = 0
    limit_down_count: Optional[int] = None
    broken_board_ratio: float = 0.0
    promotion_ratio: float = 0.0
    board_height: int = 0
    emotion_temperature: str = "unknown"
    emotion_temperature_text: str = "情绪温度数据不足"
    emotion_temperature_score: float = 0.0
    hot_industries: list[str] = Field(default_factory=list)
    hot_turnover: float = 0.0
    hot_overlap_ratio: float = 0.0
    data_quality_text: str = ""


class MarketTradingSessionResponse(BaseModel):
    updated_at: str
    is_trading_day: bool = False
    is_trading_now: bool = False
    current_time: str = ""
    timezone: str = "Asia/Shanghai"
    data_quality_text: str = ""


class SectorRelativeStrengthItem(BaseModel):
    sector_name: str
    symbol: str
    name: str = ""
    latest_price: float = 0.0
    change_pct: float = 0.0
    sector_median_change_pct: float = 0.0
    relative_strength_ratio: float | None = None
    volume_ratio: float = 0.0
    turnover_proxy: float = 0.0
    leader_score: float = 0.0
    rank: int = 0
    data_quality_text: str = ""


class SectorRelativeStrengthResponse(BaseModel):
    updated_at: str
    trade_date: str = ""
    sector_count: int = 0
    items: list[SectorRelativeStrengthItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class IntradayKeyLevelOut(BaseModel):
    level_type: str
    level_text: str
    price: float
    distance_pct: float = 0.0
    alert: bool = False


class IntradayKeyLevelResponse(BaseModel):
    symbol: str
    name: str = ""
    updated_at: str
    latest_price: float = 0.0
    vwap: float = 0.0
    entry_zone_low: float | None = None
    entry_zone_high: float | None = None
    alert_threshold_pct: float = 0.3
    alert_triggered: bool = False
    alert_text: str = ""
    levels: list[IntradayKeyLevelOut] = Field(default_factory=list)
    data_quality_text: str = ""


class SectorEtfT0Opportunity(BaseModel):
    sector_name: str
    etf_symbol: str
    etf_name: str
    source_signal_symbol: str = ""
    source_signal_name: str = ""
    source_signal_state: str = ""
    source_strategy: str = ""
    source_signal_text: str = ""
    last_price: float = 0.0
    change_pct: float = 0.0
    bias: str = "hold"
    bias_text: str = "不做T"
    confidence: float = 0.0
    entry_zone: str = ""
    sell_zone: str = ""
    stop_loss: float = 0.0
    expected_edge_pct: float = 0.0
    reason: str = ""
    risk: str = ""
    data_quality_text: str = ""


class SectorEtfT0Response(BaseModel):
    updated_at: str
    market_state: str = ""
    market_state_text: str = ""
    total: int = 0
    opportunities: list[SectorEtfT0Opportunity] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class IntradayAnomalyResponse(BaseModel):
    symbol: str
    name: str = ""
    updated_at: str
    anomaly_level: str = "normal"
    anomaly_text: str = "暂无异常"
    score: float = 0.0
    pattern: str = ""
    action_hint: str = ""
    reasons: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    data_quality_text: str = ""


class MarketModelValidationMetric(BaseModel):
    name: str
    status: str = "pending"
    sample_count: int = 0
    settled_count: int = 0
    pending_count: int = 0
    pass_rate_pct: float = 0.0
    avg_edge_pct: float = 0.0
    avg_return_1d_pct: float = 0.0
    avg_return_3d_pct: float = 0.0
    avg_max_adverse_5d_pct: float = 0.0
    false_positive_rate_pct: float = 0.0
    p_value: float = 1.0
    notes: str = ""


class MarketModelValidationResponse(BaseModel):
    model_key: str
    generated_at: str
    production_ready: bool = False
    acceptance_status: str = "pending"
    metrics: list[MarketModelValidationMetric] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PairedHedgeLegOut(BaseModel):
    role: str
    symbol: str
    name: str = ""
    side: str = "long"
    notional_ratio: float = 0.0
    latest_price: float = 0.0
    change_pct: float = 0.0
    reason: str = ""


class PairedHedgeIdeaOut(BaseModel):
    source_signal_symbol: str
    source_signal_name: str = ""
    source_strategy: str = ""
    sector_name: str = ""
    confidence: float = 0.0
    hedge_ratio: float = 0.0
    gross_exposure_pct: float = 0.0
    net_exposure_pct: float = 0.0
    estimated_beta: float = 0.0
    hedge_cost_pct: float = 0.0
    tracking_error_pct: float = 0.0
    legs: list[PairedHedgeLegOut] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)


class PairedHedgeResearchResponse(BaseModel):
    updated_at: str
    mode: str = "research_only"
    disclaimer: str = "配对/对冲研究仅用于复盘和假设分析，不自动下单，不构成真实对冲或收益承诺。"
    total: int = 0
    ideas: list[PairedHedgeIdeaOut] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
