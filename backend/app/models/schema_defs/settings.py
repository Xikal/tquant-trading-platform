from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SettingsPayload(BaseModel):
    llm_provider: str = "auto"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    data_source: str = "akshare_eastmoney"
    data_source_base_url: str = ""
    database_url: str = ""
    risk_max_single_loss_pct: float = 1.0
    risk_max_daily_loss_pct: float = 2.5
    risk_pause_after_losses: int = 3
    walk_forward_window_size: int = 3
    event_risk_enabled: bool = True
    microstructure_enabled: bool = True
    strategy_min_amount_stock: float = 30_000_000.0
    strategy_min_amount_etf: float = 15_000_000.0
    strategy_min_amplitude_pct: float = 0.6
    strategy_max_amplitude_pct: float = 15.0
    strategy_max_atr_pct: float = 4.0
    strategy_open_phase_end_hhmm: int = 935
    strategy_open_phase_min_tradability: float = 60.0
    strategy_min_profit_pct: float = 3.0
    strategy_min_profit_stock_pct: float = 3.0
    strategy_min_profit_etf_pct: float = 1.5
    strategy_slippage_stock_bps: float = 7.0
    strategy_slippage_etf_bps: float = 4.0
    llm_api_key_configured: bool = False
    database_url_configured: bool = False
    admin_auth_required: bool = False


class SettingsUpdate(BaseModel):
    llm_provider: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None
    data_source: Optional[str] = None
    data_source_base_url: Optional[str] = None
    database_url: Optional[str] = None
    risk_max_single_loss_pct: Optional[float] = None
    risk_max_daily_loss_pct: Optional[float] = None
    risk_pause_after_losses: Optional[int] = None
    walk_forward_window_size: Optional[int] = None
    event_risk_enabled: Optional[bool] = None
    microstructure_enabled: Optional[bool] = None
    strategy_min_amount_stock: Optional[float] = None
    strategy_min_amount_etf: Optional[float] = None
    strategy_min_amplitude_pct: Optional[float] = None
    strategy_max_amplitude_pct: Optional[float] = None
    strategy_max_atr_pct: Optional[float] = None
    strategy_open_phase_end_hhmm: Optional[int] = None
    strategy_open_phase_min_tradability: Optional[float] = None
    strategy_min_profit_pct: Optional[float] = None
    strategy_min_profit_stock_pct: Optional[float] = None
    strategy_min_profit_etf_pct: Optional[float] = None
    strategy_slippage_stock_bps: Optional[float] = None
    strategy_slippage_etf_bps: Optional[float] = None


class DatabaseCheckRequest(BaseModel):
    database_url: str = Field(..., min_length=1)


class DatabaseCheckResponse(BaseModel):
    ok: bool
    dialect: str
    database: str
    masked_url: str
    tables: List[str]
    message: str


class DatabaseMigrationRequest(BaseModel):
    target_database_url: str = Field(..., min_length=1)
    source_database_url: str = "sqlite:///./data/t_quant.db"
    overwrite: bool = False
    activate_on_restart: bool = True


class DatabaseMigrationResponse(BaseModel):
    ok: bool
    source_database_url: str
    target_database_url: str
    scope: str = "full_sqlalchemy_metadata"
    copied_tables: List[str] = Field(default_factory=list)
    cleared_tables: List[str] = Field(default_factory=list)
    skipped_tables: List[str] = Field(default_factory=list)
    failed_tables: List[str] = Field(default_factory=list)
    copied_rows: Dict[str, int]
    total_rows: int
    activated_on_restart: bool
    recovery_hint: str = ""
    message: str


class RuntimeStatusResponse(BaseModel):
    app_name: str
    api_prefix: str
    database_backend: str
    database_url_masked: str
    runtime_database_url_masked: str = ""
    runtime_env_path: str
    runtime_env_exists: bool
    runtime_database_override: bool
    runtime_database_matches_settings: bool = True
    runtime_llm_secret_persisted: bool = False
    settings_consistency_status: str = "ok"
    settings_consistency_text: str = "运行时配置一致"
    frontend_dist_path: str
    frontend_dist_ready: bool
    llm_configured: bool
    data_source: str
    data_source_base_url: str
    cors_origins: List[str]
    ready_checks: Dict[str, bool]


class FactorSpecOut(BaseModel):
    name: str
    weight: float
    data_dependencies: List[str] = Field(default_factory=list)
    applicable_strategies: List[str] = Field(default_factory=list)
    activation_condition: str = "always"
    status: str = "active"
    status_text: str = "已启用"


class FactorWeightsResponse(BaseModel):
    weights: Dict[str, float]
    defaults: Dict[str, float]
    factors: List[FactorSpecOut]


class FactorWeightsUpdate(BaseModel):
    weights: Dict[str, float] = Field(default_factory=dict)


class UserSectorExclusionsResponse(BaseModel):
    available_sectors: List[str] = Field(default_factory=list)
    excluded_sectors: List[str] = Field(default_factory=list)
    excluded_count: int = 0
    updated_at: str = ""


class UserSectorExclusionsUpdate(BaseModel):
    excluded_sectors: List[str] = Field(default_factory=list, max_length=300)
