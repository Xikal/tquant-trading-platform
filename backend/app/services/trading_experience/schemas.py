from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DataQuality = Literal["ok", "insufficient", "no_data", "blocked", "stale", "research_only"]


class TradingExperienceMeta(BaseModel):
    data_quality: DataQuality = "insufficient"
    as_of: datetime
    engine_version: str
    source: str = "local_snapshot"
    research_only: bool = True


class TradingExperienceReadinessResponse(TradingExperienceMeta):
    enabled: bool
    flags: dict[str, bool] = Field(default_factory=dict)
    disabled_reasons: list[str] = Field(default_factory=list)
    worker_task_types: list[str] = Field(default_factory=list)


class ReviewPoolItem(BaseModel):
    pool_date: str
    symbol: str
    name: str = ""
    status: Literal["in_pool", "retained", "dropped"]
    entry_pct: float
    volume_ratio: float
    mainline_state: str = "unknown"
    sector_role: str = "unknown"
    drop_reason: str = ""
    tracked_days: int = 0
    evidence: list[str] = Field(default_factory=list)
    data_quality: DataQuality
    as_of: datetime
    engine_version: str


class ReviewPoolResponse(TradingExperienceMeta):
    enabled: bool
    pool_date: str | None = None
    items: list[ReviewPoolItem] = Field(default_factory=list)
    total: int = 0


TradeAction = Literal["buy", "sell", "trim", "add", "t_trade", "note"]


class TradeJournalEntryCreate(BaseModel):
    account_id: int | None = None
    symbol: str
    action: TradeAction
    reason_text: str = ""
    signal_source: str = ""
    discipline_flags: dict[str, bool] = Field(default_factory=dict)
    mistake_tags: list[str] = Field(default_factory=list)


class TradeJournalEntryOut(TradeJournalEntryCreate):
    entry_id: int
    user_id: int | None = None
    data_quality: DataQuality = "ok"
    as_of: datetime
    engine_version: str
    source: str = "manual"
    research_only: bool = True
    created_at: datetime
    updated_at: datetime


class TradeJournalResponse(TradingExperienceMeta):
    enabled: bool
    items: list[TradeJournalEntryOut] = Field(default_factory=list)
    total: int = 0


class VolumePositionTag(BaseModel):
    symbol: str
    trade_date: str
    tag_code: str
    level: Literal["info", "warn"]
    evidence: list[str] = Field(default_factory=list)
    explanation: str
    data_quality: DataQuality
    as_of: datetime
    engine_version: str


class VolumePositionTagResponse(TradingExperienceMeta):
    enabled: bool
    symbol: str
    items: list[VolumePositionTag] = Field(default_factory=list)


class RelativeStrengthItem(BaseModel):
    symbol: str
    trade_date: str
    index_code: str
    sector_code: str
    stock_pct: float
    index_pct: float
    sector_pct: float
    rs_vs_index: float
    rs_vs_sector: float
    sector_rank: int
    resilience_flag: Literal["resilient", "follow_down", "neutral"]
    data_quality: DataQuality
    as_of: datetime


class RelativeStrengthResponse(TradingExperienceMeta):
    enabled: bool
    items: list[RelativeStrengthItem] = Field(default_factory=list)
    total: int = 0


class HoldingDisciplineHint(BaseModel):
    account_id: int
    symbol: str
    hint_code: Literal["trailing_stop", "no_add_down_warning", "break_down", "emotional_pullback", "watch_cadence"]
    level: Literal["info", "warn"]
    evidence: list[str] = Field(default_factory=list)
    data_quality: DataQuality
    as_of: datetime


class HoldingDisciplineResponse(TradingExperienceMeta):
    enabled: bool
    account_id: int | None = None
    items: list[HoldingDisciplineHint] = Field(default_factory=list)
    total: int = 0


LimitUpFollowthroughStatus = Literal["research_only", "observed", "blocked"]


class LimitUpFollowthroughItem(BaseModel):
    symbol: str
    limit_up_date: str
    pattern_code: str
    days_since: int
    evidence: list[str] = Field(default_factory=list)
    backtest_winrate: float | None = None
    backtest_pf: float | None = None
    backtest_max_drawdown: float | None = None
    sample_count: int = 0
    quarter_stability: str = "blocked"
    status: LimitUpFollowthroughStatus = "research_only"
    data_quality: DataQuality
    as_of: datetime


class LimitUpFollowthroughResponse(TradingExperienceMeta):
    enabled: bool
    items: list[LimitUpFollowthroughItem] = Field(default_factory=list)
    total: int = 0
    backtest_gate: Literal["blocked", "passed", "failed"] = "blocked"
    gate_reasons: list[str] = Field(default_factory=list)
    backtest_window_months: int = 24


class TTradeAttributionItem(BaseModel):
    account_id: int
    symbol: str
    period: str
    t_trade_count: int
    realized_cost_delta: float
    win_rate: float
    sell_fly_count: int
    vs_no_t_trade_return_delta: float | None = None
    minute_data_coverage: float
    completeness_issues: list[str] = Field(default_factory=list)
    comparison_method: str = "paired_cashflow_vs_hold"
    key_level_state: str = "insufficient"
    discipline_notes: list[str] = Field(default_factory=list)
    data_quality: DataQuality
    as_of: datetime


class TTradeAttributionResponse(TradingExperienceMeta):
    enabled: bool
    account_id: int | None = None
    items: list[TTradeAttributionItem] = Field(default_factory=list)
    total: int = 0
