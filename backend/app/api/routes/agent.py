from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.agent_providers.factory import create_agent_provider
from app.agent_tools.policy import AgentPolicy
from app.agent_tools.registry import list_tool_definitions
from app.core.admin_auth import require_admin_auth
from app.core.config import get_settings
from app.core.database import get_db
from app.models.schema_defs.agent import (
    AgentAnalysisRequest,
    AgentAnalysisResponse,
    AgentDailyReportResponse,
    AgentHealthResponse,
    AgentNotificationTestRequest,
    AgentNotificationTestResponse,
    AgentPriorityBoardResponse,
    AgentProviderStatusResponse,
    AgentToolInvokeRequest,
    AgentToolResult,
    AgentWatchlistContextResponse,
)
from app.services.agent_context_service import AgentContextService
from app.services.agent_report_service import AgentReportService

router = APIRouter(prefix="/agent")

context_service = AgentContextService()
report_service = AgentReportService()


@router.get("/health", response_model=AgentHealthResponse)
def agent_health(db: Session = Depends(get_db)) -> AgentHealthResponse:
    return context_service.health(db)


@router.get("/context/watchlist", response_model=AgentWatchlistContextResponse)
def agent_watchlist_context(db: Session = Depends(get_db)) -> AgentWatchlistContextResponse:
    return context_service.watchlist_context(db)


@router.get("/context/priority-board", response_model=AgentPriorityBoardResponse)
def agent_priority_board(
    limit: int = Query(default=12, ge=1, le=50),
    db: Session = Depends(get_db),
) -> AgentPriorityBoardResponse:
    return context_service.priority_board(db, limit=limit)


@router.post("/context/analysis", response_model=AgentAnalysisResponse)
def agent_analysis(payload: AgentAnalysisRequest, db: Session = Depends(get_db)) -> AgentAnalysisResponse:
    return context_service.analysis(db, payload)


@router.get("/reports/daily", response_model=AgentDailyReportResponse)
def agent_daily_report(db: Session = Depends(get_db)) -> AgentDailyReportResponse:
    return report_service.daily_report(db)


@router.post("/notify/test", response_model=AgentNotificationTestResponse)
def agent_notify_test(payload: AgentNotificationTestRequest) -> AgentNotificationTestResponse:
    return AgentNotificationTestResponse(
        ok=True,
        channel=payload.channel,
        message="notification adapter not configured",
    )


@router.get("/provider/status", response_model=AgentProviderStatusResponse)
def agent_provider_status(db: Session = Depends(get_db)) -> AgentProviderStatusResponse:
    settings = get_settings()
    provider = create_agent_provider(db)
    policy = AgentPolicy()
    tools = list_tool_definitions()
    allowed_tools = [tool.name for tool in tools if tool.enabled and policy.check_tool_allowed(tool) is None]
    disabled_tools = [tool.name for tool in tools if not tool.enabled or policy.check_tool_allowed(tool) is not None]
    health = provider.health()
    return AgentProviderStatusResponse(
        provider=provider.name,
        available=health.available,
        external_agent=health.external_agent,
        write_tools_enabled=settings.agent_enable_write_tools,
        notify_tools_enabled=settings.agent_enable_notify_tools,
        audit_enabled=settings.agent_audit_enabled,
        tool_count=len(tools),
        enabled_tools=allowed_tools,
        disabled_tools=disabled_tools,
        warnings=health.warnings,
    )


@router.post("/provider/invoke", response_model=AgentToolResult)
def agent_provider_invoke(
    payload: AgentToolInvokeRequest,
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> AgentToolResult:
    provider = create_agent_provider(db)
    return provider.invoke_tool(payload.tool_name, payload.arguments)
