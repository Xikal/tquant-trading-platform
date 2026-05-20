from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.schema_defs.paper import (
    PaperAccountOut,
    PaperAgentRunOut,
    PaperGroupedPerformanceOut,
    PaperOrderOut,
    PaperPerformanceOut,
    PaperPositionOut,
    PaperSectorEtfT0PerformanceOut,
    PaperStockPnlResponse,
    PaperTagPerformanceOut,
    PaperTradeOut,
)
from app.models.schema_defs.research import RiskEventOut
from app.models.schema_defs.backtest import BacktestRunListResponse, BacktestVerdictThresholdsResponse
from app.models.schema_defs.strategy_meta import StrategyMetaResponse, StrategyPresetResponse


class BffPartialError(BaseModel):
    source: str
    detail: str


class BffManifestResponse(BaseModel):
    api_version: str = "v1"
    bff_version: str = "v1"
    gateway_prefix: str = "/api"
    modules: list[str] = Field(default_factory=list)


class PaperWorkspaceBffResponse(BaseModel):
    api_version: str = "v1"
    generated_at: str
    account: PaperAccountOut | None = None
    positions: list[PaperPositionOut] = Field(default_factory=list)
    orders: list[PaperOrderOut] = Field(default_factory=list)
    trades: list[PaperTradeOut] = Field(default_factory=list)
    stock_pnl: PaperStockPnlResponse | None = None
    performance: PaperPerformanceOut | None = None
    sector_etf_t0_performance: PaperSectorEtfT0PerformanceOut | None = None
    strategy_performance: list[PaperGroupedPerformanceOut] = Field(default_factory=list)
    market_performance: list[PaperGroupedPerformanceOut] = Field(default_factory=list)
    tag_performance: list[PaperTagPerformanceOut] = Field(default_factory=list)
    risk_events: list[RiskEventOut] = Field(default_factory=list)
    auto_trading_status: dict[str, Any] = Field(default_factory=dict)
    auto_trading_runs: list[PaperAgentRunOut] = Field(default_factory=list)
    partial_errors: list[BffPartialError] = Field(default_factory=list)


class StrategyWorkspaceBffResponse(BaseModel):
    api_version: str = "v1"
    generated_at: str
    strategy_meta: StrategyMetaResponse | None = None
    presets: StrategyPresetResponse | None = None
    recent_runs: BacktestRunListResponse | None = None
    verdict_thresholds: BacktestVerdictThresholdsResponse | None = None
    partial_errors: list[BffPartialError] = Field(default_factory=list)
