from __future__ import annotations

import os
import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, List, Union

from dotenv import dotenv_values
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
BASE_ENV_PATH = Path(os.getenv("BASE_ENV_PATH", BACKEND_DIR / ".env")).expanduser()
RUNTIME_ENV_PATH = Path(
    os.getenv("RUNTIME_ENV_PATH", BACKEND_DIR / "data" / "runtime.env")
).expanduser()


def _load_file_overrides() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BASE_ENV_PATH, RUNTIME_ENV_PATH):
        if not path.exists():
            continue
        for key, value in dotenv_values(path).items():
            if value is None or key in os.environ:
                continue
            merged[key.lower()] = value
    return merged


class AppSettings(BaseSettings):
    app_name: str = "维斯量化交易平台"
    api_prefix: str = "/api"
    database_url: str = "sqlite:///./data/t_quant.db"
    cors_origins: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    default_data_source: str = "akshare_eastmoney"
    http_timeout: int = 12
    market_quote_timeout_seconds: float = 3.0
    market_batch_timeout_seconds: float = 8.0
    market_intraday_timeout_seconds: float = 5.0
    market_calendar_timeout_seconds: float = 5.0
    akshare_timeout_seconds: float = 12.0
    notification_timeout_seconds: float = 8.0
    app_mobile_quick_history_timeout: float = 10.0
    runtime_background_jobs_enabled: bool = False
    runtime_background_jobs_on_sqlite: bool = True
    runtime_background_role: str = "scheduler"
    runtime_worker_poll_interval_seconds: float = 5.0
    decision_context_enabled: bool = True
    market_gate_production_enabled: bool = True
    sector_leader_gate_production_enabled: bool = True
    hard_risk_filter_production_enabled: bool = True
    intraday_entry_production_boost_enabled: bool = False
    event_risk_production_block_enabled: bool = False
    promotion_engine_auto_apply_enabled: bool = False
    data_quality_sla_enabled: bool = True
    data_repair_auto_enabled: bool = False
    track_record_enabled: bool = True
    drift_alert_enabled: bool = False
    tquant_research_jobs_enabled: bool = False
    tquant_ml_jobs_enabled: bool = False
    tquant_factor_jobs_enabled: bool = False
    tquant_strategy_evolution_enabled: bool = False
    trading_experience_suite_enabled: bool = False
    trade_review_suite_enabled: bool = False
    vp_position_tags_enabled: bool = False
    relative_strength_board_enabled: bool = False
    holding_discipline_assistant_enabled: bool = False
    limit_up_followthrough_enabled: bool = False
    t_trade_discipline_enabled: bool = False
    platform_autopilot_enabled: bool = True
    platform_autopilot_notify_enabled: bool = False
    platform_autopilot_interval_seconds: int = 300
    platform_autopilot_failed_task_window_hours: int = 24
    redis_url: str = ""
    db_pool_size: int = 12
    db_max_overflow: int = 24
    db_pool_recycle: int = 1800
    db_pool_timeout: int = 30
    runtime_event_pubsub_backend: str = "auto"
    runtime_event_stream_timeout_seconds: int = 360
    runtime_event_stream_poll_seconds: float = 1.0
    schema_compat_repair_enabled: bool = False
    schema_compat_verify_on_startup: bool = False
    legacy_route_compat_enabled: bool = False
    max_request_body_bytes: int = 1_048_576
    structured_logs: bool = False
    tquant_market_service_url: str = ""
    tquant_bff_gateway_url: str = ""
    tquant_bff_shadow_enabled: bool = False
    tquant_market_read_service_url: str = ""
    tquant_go_scan_worker_url: str = ""
    tquant_go_scan_enabled: bool = True
    tquant_strategy_service_url: str = ""
    tquant_backtest_service_url: str = ""
    tquant_trade_service_url: str = ""
    tquant_factor_service_url: str = ""
    tquant_admin_service_url: str = ""
    tquant_internal_service_token: str = ""
    tquant_service_call_timeout_seconds: float = 5.0
    tquant_service_circuit_breaker_seconds: float = 30.0
    bff_workspace_cache_enabled: bool = True
    monitor_bff_aggregate_enabled: bool = True
    bff_monitor_cache_ttl_seconds: int = 5
    bff_paper_cache_ttl_seconds: int = 3
    bff_strategy_cache_ttl_seconds: int = 30
    bff_settings_cache_ttl_seconds: int = 30
    monitor_bff_source_budget_enabled: bool = True
    quote_cache_demand_warmup_enabled: bool = True
    read_model_live_overlay_enabled: bool = True
    priority_board_empty_fallback_to_last_snapshot: bool = True
    priority_board_overlay_cache_enabled: bool = True
    priority_board_overlay_cache_ttl_seconds: int = 2
    priority_board_filter_cache_enabled: bool = True
    priority_board_stable_read_model_enabled: bool = True
    priority_board_stable_read_model_ttl_seconds: int = 45
    response_payload_metrics_enabled: bool = True
    distributed_cache_fail_open_enabled: bool = True
    derived_indicator_cache_enabled: bool = True
    derived_indicator_cache_ttl_seconds: int = 120
    rust_finance_math_enabled: bool = True
    app_workers: int = 1
    global_rate_limit_backend: str = "memory"
    global_rate_limit_max_calls: int = 30
    global_rate_limit_window_seconds: int = 1
    admin_api_token: str = ""
    auth_secret_key: str = ""
    tquant_settings_encryption_key: str = ""
    auth_cookie_secure: bool = True
    auth_allow_insecure_http_cookie: bool = False
    app_environment: str = "development"
    auth_cookie_samesite: str = "strict"
    auth_access_token_minutes: int = 15
    auth_refresh_token_days: int = 7
    auth_allow_legacy_tokens: bool = False
    auth_login_lockout_threshold: int = 5
    auth_login_lockout_minutes: int = 15
    auth_allowed_usernames: Annotated[List[str], NoDecode] = Field(default_factory=list)
    auth_require_mfa_for_login: bool = False
    agent_provider: str = "none"
    agent_api_base: str = "http://127.0.0.1:18090/api"
    agent_api_token: str = ""
    agent_tokens: dict[str, str] = Field(default_factory=dict)
    agent_mcp_server_url: str = ""
    agent_http_gateway_url: str = ""
    agent_timeout_seconds: int = 10
    agent_enable_write_tools: bool = False
    agent_enable_notify_tools: bool = False
    agent_allowed_capabilities: Annotated[List[str], NoDecode] = Field(default_factory=list)
    agent_audit_enabled: bool = True
    agent_quality_min_score: float = 0.72
    notification_feishu_webhook_url: str = ""
    notification_feishu_secret: str = ""
    notification_signal_cooldown_minutes: int = 240
    notification_signal_scan_enabled: bool = True
    notification_signal_scan_interval_seconds: int = 120
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_verification_token: str = ""
    feishu_encrypt_key: str = ""
    langgraph_api_url: str = ""
    langgraph_api_key: str = ""
    openai_agents_api_url: str = ""
    openai_agents_api_key: str = ""
    hermes_api_url: str = ""
    hermes_api_key: str = ""
    openclaw_api_url: str = ""
    openclaw_api_key: str = ""
    crewai_api_url: str = ""
    crewai_api_key: str = ""
    pydantic_ai_api_url: str = ""
    pydantic_ai_api_key: str = ""
    openbb_api_url: str = ""
    openbb_api_key: str = ""
    market_data_provider_order: str = "tencent,eastmoney,akshare,sina"
    market_provider_router_enabled: bool = True
    market_provider_circuit_failure_threshold: int = 3
    # First provider circuit open cooldown. Opening auction often recovers
    # quickly; keep this short and let repeated failures back off.
    market_provider_circuit_cooldown_seconds: int = 20
    market_provider_circuit_cooldown_second_seconds: int = 45
    market_provider_circuit_cooldown_max_seconds: int = 90
    market_provider_slow_call_ms: int = 3000
    market_provider_call_timeout_seconds: float = 4.0
    market_quote_async_provider_enabled: bool = True
    market_quote_async_provider_chunk_size: int = 60
    market_quote_async_provider_concurrency: int = 4
    bff_workspace_timeout_seconds: float = 8.0
    market_akshare_quote_fallback_enabled: bool = False
    eastmoney_bypass_proxy: bool = False
    quant_parameter_default_version: str = "quant-params-v1"
    ml_signal_model_dir: str = "data/ml_models"
    ml_signal_artifact_remote_dir: str = ""
    ml_signal_min_production_samples: int = 1000
    ml_signal_min_production_accuracy: float = 0.60
    ml_signal_min_production_auc: float = 0.65
    ml_signal_cv_folds: int = 5
    ml_signal_min_cv_accuracy: float = 0.60
    ml_signal_min_cv_auc: float = 0.65
    ml_signal_max_cv_accuracy_std: float = 0.08
    ml_signal_max_cv_auc_std: float = 0.06
    enable_deep_rl: bool = False
    enable_deep_rl_training: bool = False
    paper_auto_trading_enabled: bool = False
    paper_auto_trading_interval: int = 120
    paper_auto_trading_max_orders: int = 5
    paper_auto_trading_dry_run: bool = False
    paper_auto_trading_min_score: int = 75
    paper_exit_model_enabled: bool = True
    paper_exit_model_artifact_path: str = ""
    paper_exit_model_min_confidence: float = 0.55
    paper_exit_model_strong_confidence: float = 0.75
    main_force_model_enabled: bool = True
    main_force_model_shadow_enabled: bool = True
    main_force_model_display_enabled: bool = True
    main_force_model_ranking_enabled: bool = False
    main_force_model_paper_display_enabled: bool = True
    main_force_model_paper_shadow_enabled: bool = True
    main_force_model_paper_suggestion_enabled: bool = False
    main_force_model_max_rank_bonus: float = 4.0
    main_force_model_min_confidence: float = 0.58
    main_force_model_min_score: float = 55.0
    main_force_model_paper_max_position_pct: float = 3.0
    main_force_model_paper_min_confidence: float = 0.62
    main_force_model_shadow_sample_min: int = 300
    main_force_model_shadow_settled_min: int = 120
    main_force_model_min_success_rate_pct: float = 52.0
    main_force_model_min_profit_factor: float = 1.35
    main_force_model_allowed_strategies: str = (
        "leader_pullback_band,volume_shrink,breakout_support,n_pattern_long_wash,"
        "core_midcap_vwap_ma5_retrace"
    )
    market_review_enabled: bool = True
    paper_perf_archive_enabled: bool = True
    paper_perf_archive_time: str = "15:05"
    paper_perf_ai_report_enabled: bool = True
    strategy_validation_monthly_enabled: bool = True
    analytics_24m_report_schedule_enabled: bool = False
    analytics_24m_report_interval_hours: int = 24
    strategy_validation_monthly_lookback_days: int = 252
    strategy_validation_monthly_max_signals_per_day: int = 8
    evolution_scheduler_weekday: int = 4
    evolution_scheduler_hour: int = 16
    evolution_scheduler_minute: int = 5
    evolution_due_minute: int = 5
    evolution_drift_scheduler_day: int = 1
    evolution_drift_scheduler_hour: int = 16
    evolution_drift_scheduler_minute: int = 35
    evolution_drift_due_minute: int = 35
    evolution_ledger_scheduler_hour: int = 19
    evolution_ledger_scheduler_minute: int = 0
    evolution_ledger_due_minute: int = 0
    evolution_ledger_gap_alert_threshold: float = 1.0

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: Union[str, List[str]]) -> List[str]:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return []

    @field_validator("auth_allowed_usernames", mode="before")
    @classmethod
    def parse_allowed_usernames(cls, value: Union[str, List[str]]) -> List[str]:
        if isinstance(value, list):
            return [str(item).strip().lower() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [item.strip().lower() for item in value.split(",") if item.strip()]
        return []

    @field_validator("agent_allowed_capabilities", mode="before")
    @classmethod
    def parse_agent_allowed_capabilities(cls, value: Union[str, List[str]]) -> List[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return []

    @field_validator("agent_tokens", mode="before")
    @classmethod
    def parse_agent_tokens(cls, value: Any) -> dict[str, str]:
        if isinstance(value, dict):
            return {str(key).strip(): str(item).strip() for key, item in value.items() if str(key).strip()}
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return {}
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError:
                return {}
            if isinstance(parsed, dict):
                return {
                    str(key).strip(): str(item).strip()
                    for key, item in parsed.items()
                    if str(key).strip()
                }
        return {}


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings(**_load_file_overrides())
