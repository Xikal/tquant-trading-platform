from __future__ import annotations

from sqlalchemy.orm import Session

from app.agent_tools.audit import agent_audit_metrics
from app.core.task_manager import task_manager
from app.core.timing import request_timing_snapshot
from app.services.latest_data_status import latest_data_status
from app.services.market.local_quote_cache import local_quote_cache_metrics_snapshot
from app.services.market.providers.circuit import provider_metrics_snapshot
from app.services.market.providers.probe import DataSourceProbeService


def build_admin_metrics_snapshot(db: Session) -> dict:
    snapshot = request_timing_snapshot()
    snapshot["agent_tools"] = agent_audit_metrics(db)
    snapshot["market_providers"] = provider_metrics_snapshot()
    snapshot["market_data_sources"] = DataSourceProbeService().probe().model_dump()
    snapshot["local_quote_cache"] = local_quote_cache_metrics_snapshot()
    snapshot["latest_low_buy_data"] = latest_data_status(db)
    return snapshot


def build_admin_task_snapshot() -> dict:
    return {"items": task_manager.snapshot()}
