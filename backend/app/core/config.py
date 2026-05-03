from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, List, Union

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
    app_mobile_quick_history_timeout: float = 10.0
    runtime_background_jobs_enabled: bool = True
    runtime_background_jobs_on_sqlite: bool = False
    max_request_body_bytes: int = 1_048_576
    structured_logs: bool = False
    admin_api_token: str = ""
    auth_secret_key: str = ""
    auth_cookie_secure: bool = False
    auth_access_token_minutes: int = 720
    auth_refresh_token_days: int = 90
    auth_allowed_usernames: Annotated[List[str], NoDecode] = Field(default_factory=list)
    agent_provider: str = "none"
    agent_api_base: str = "http://127.0.0.1:18090/api"
    agent_api_token: str = ""
    agent_mcp_server_url: str = ""
    agent_http_gateway_url: str = ""
    agent_timeout_seconds: int = 10
    agent_enable_write_tools: bool = False
    agent_enable_notify_tools: bool = False
    agent_audit_enabled: bool = True
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


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings(**_load_file_overrides())
