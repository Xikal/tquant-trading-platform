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
    hot_industries: list[str] = Field(default_factory=list)
    hot_turnover: float = 0.0
    hot_overlap_ratio: float = 0.0
    data_quality_text: str = ""


class SectorEtfT0Opportunity(BaseModel):
    sector_name: str
    etf_symbol: str
    etf_name: str
    source_signal_symbol: str = ""
    source_signal_name: str = ""
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
    pass_rate_pct: float = 0.0
    avg_edge_pct: float = 0.0
    notes: str = ""


class MarketModelValidationResponse(BaseModel):
    model_key: str
    generated_at: str
    production_ready: bool = False
    acceptance_status: str = "pending"
    metrics: list[MarketModelValidationMetric] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
