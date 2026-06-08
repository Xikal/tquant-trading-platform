from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.schema_defs.market import (
    IntradayMarketPulse,
    MarketBreadthResponse,
    MarketHourlySnapshotHistoryOut,
    MarketReviewReportOut,
    MarketReviewStatusOut,
    PairedHedgeResearchResponse,
    SectorRelativeStrengthResponse,
)
from app.models.schema_defs.monitor import MonitorSnapshotResponse
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
from app.models.schema_defs.screener import LowBuyStrategyGovernanceResponse
from app.models.schema_defs.settings import (
    FactorWeightsResponse,
    RuntimeStatusResponse,
    SettingsPayload,
    UserSectorExclusionsResponse,
)
from app.models.schema_defs.strategy_meta import StrategyMetaResponse, StrategyPresetResponse
from app.models.schema_defs.strategy_tracking import (
    StrategyTrackingHoldingAnalysisResponse,
    StrategyTrackingItemOut,
    StrategyTrackingPerformanceOut,
    StrategyTrackingReviewResponse,
    StrategyTrackingSegmentOut,
    StrategyTrackingShadowObservationOut,
    StrategyTrackingSummaryOut,
)

BFF_SCHEMA_VERSION = "v16"


class BffPartialError(BaseModel):
    source: str
    detail: str
    reason: str = "other"
    status_code: int | None = None
    timeout_ms: int | None = None
    fallback_source: str = "python_local"
    message: str = ""
    elapsed_ms: int | None = None


class BffSourceTiming(BaseModel):
    source: str
    elapsed_ms: int = 0
    status: str = "ok"
    timeout_ms: int | None = None
    reason: str = ""


class BffWorkspaceManifest(BaseModel):
    path: str
    schema_version: str = BFF_SCHEMA_VERSION
    model: str


class BffManifestResponse(BaseModel):
    api_version: str = "v1"
    bff_version: str = "v1"
    schema_version: str = BFF_SCHEMA_VERSION
    gateway_prefix: str = "/api"
    modules: list[str] = Field(default_factory=list)
    workspaces: dict[str, BffWorkspaceManifest] = Field(default_factory=dict)


class MonitorWorkspaceBffResponse(BaseModel):
    api_version: str = "v1"
    schema_version: str = BFF_SCHEMA_VERSION
    generated_at: str
    stale: bool = False
    stale_reason: str = ""
    refresh_queued: bool = False
    monitor_snapshot: MonitorSnapshotResponse | None = None
    market_breadth: MarketBreadthResponse | None = None
    market_pulse: IntradayMarketPulse | None = None
    hourly_snapshot_history: list[MarketHourlySnapshotHistoryOut] = Field(default_factory=list)
    review_status: MarketReviewStatusOut | None = None
    review_reports: list[MarketReviewReportOut] = Field(default_factory=list)
    sector_relative_strength: SectorRelativeStrengthResponse | None = None
    paired_hedge: PairedHedgeResearchResponse | None = None
    runtime: RuntimeStatusResponse | None = None
    partial_errors: list[BffPartialError] = Field(default_factory=list)
    source_timings: list[BffSourceTiming] = Field(default_factory=list)


class PaperWorkspaceBffResponse(BaseModel):
    api_version: str = "v1"
    schema_version: str = BFF_SCHEMA_VERSION
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
    schema_version: str = BFF_SCHEMA_VERSION
    generated_at: str
    strategy_meta: StrategyMetaResponse | None = None
    presets: StrategyPresetResponse | None = None
    recent_runs: BacktestRunListResponse | None = None
    verdict_thresholds: BacktestVerdictThresholdsResponse | None = None
    items: list[StrategyTrackingItemOut] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0
    sort: str = "max_gain_desc"
    summary: StrategyTrackingSummaryOut | None = None
    performance: list[StrategyTrackingPerformanceOut] = Field(default_factory=list)
    market_segments: list[StrategyTrackingSegmentOut] = Field(default_factory=list)
    shadow_observations: list[StrategyTrackingShadowObservationOut] = Field(default_factory=list)
    holding_analysis: StrategyTrackingHoldingAnalysisResponse | None = None
    review: StrategyTrackingReviewResponse | None = None
    tracking_notes: list[str] = Field(default_factory=list)
    partial_errors: list[BffPartialError] = Field(default_factory=list)


class SettingsWorkspaceBffResponse(BaseModel):
    api_version: str = "v1"
    schema_version: str = BFF_SCHEMA_VERSION
    generated_at: str
    settings: SettingsPayload | None = None
    sector_exclusions: UserSectorExclusionsResponse | None = None
    strategy_governance: LowBuyStrategyGovernanceResponse | None = None
    runtime: RuntimeStatusResponse | None = None
    factor_weights: FactorWeightsResponse | None = None
    admin_tasks: dict[str, Any] | None = None
    admin_metrics: dict[str, Any] | None = None
    admin_enabled: bool = False
    partial_errors: list[BffPartialError] = Field(default_factory=list)
