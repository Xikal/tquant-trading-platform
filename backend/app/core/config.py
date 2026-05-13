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
    runtime_worker_poll_interval_seconds: float = 5.0
    redis_url: str = ""
    runtime_event_pubsub_backend: str = "auto"
    runtime_event_stream_timeout_seconds: int = 360
    runtime_event_stream_poll_seconds: float = 1.0
    schema_compat_repair_enabled: bool = False
    schema_compat_verify_on_startup: bool = False
    legacy_route_compat_enabled: bool = False
    max_request_body_bytes: int = 1_048_576
    structured_logs: bool = False
    global_rate_limit_backend: str = "memory"
    global_rate_limit_max_calls: int = 30
    global_rate_limit_window_seconds: int = 1
    admin_api_token: str = ""
    auth_secret_key: str = ""
    auth_cookie_secure: bool = True
    app_environment: str = "development"
    auth_cookie_samesite: str = "strict"
    auth_access_token_minutes: int = 60
    auth_refresh_token_days: int = 30
    auth_allow_legacy_tokens: bool = False
    auth_login_lockout_threshold: int = 5
    auth_login_lockout_minutes: int = 15
    auth_allowed_usernames: Annotated[List[str], NoDecode] = Field(default_factory=list)
    auth_require_mfa_for_login: bool = False
    auth_require_mfa_for_paper_trade: bool = False
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
    market_provider_circuit_cooldown_seconds: int = 60
    market_provider_slow_call_ms: int = 3000
    market_provider_call_timeout_seconds: float = 4.0
    market_akshare_quote_fallback_enabled: bool = False
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
    paper_auto_trading_enabled: bool = True
    paper_auto_trading_interval: int = 120
    paper_auto_trading_max_orders: int = 5
    paper_auto_trading_dry_run: bool = False
    paper_auto_trading_min_score: int = 75
    paper_perf_archive_enabled: bool = True
    paper_perf_archive_time: str = "15:05"
    paper_perf_ai_report_enabled: bool = True
    strategy_validation_monthly_enabled: bool = True
    strategy_validation_monthly_lookback_days: int = 252
    strategy_validation_monthly_max_signals_per_day: int = 8

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
