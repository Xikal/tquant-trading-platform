from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.agent_helpers import (
    agent_backtest_strategy as run_agent_backtest_strategy,
    agent_compare_strategies as run_agent_compare_strategies,
    agent_create_paper_order as run_agent_create_paper_order,
    agent_market_sentiment as run_agent_market_sentiment,
    agent_position_t_signal as run_agent_position_t_signal,
    agent_sector_heatmap as run_agent_sector_heatmap,
    audit_log_out,
)
from app.agent_providers.factory import create_agent_provider
from app.agent_tools.audit import agent_audit_summary
from app.agent_tools.policy import AgentPolicy
from app.agent_tools.registry import list_tool_definitions
from app.core.admin_auth import require_admin_auth
from app.core.agent_auth import require_agent_tool_permission, require_current_user_or_agent_token
from app.core.config import get_settings
from app.core.database import get_db
from app.models.entities import AgentAuditLog, User
from app.models.schema_defs.agent import (
    AgentAnalysisRequest,
    AgentAnalysisResponse,
    AgentAuditLogOut,
    AgentAuditSummaryResponse,
    AgentBacktestRequest,
    AgentBacktestResponse,
    AgentCompareStrategiesRequest,
    AgentCompareStrategiesResponse,
    AgentComprehensiveAnalysisRequest,
    AgentCrossValidationRequest,
    AgentDailyReportPushRequest,
    AgentDailyReportPushResponse,
    AgentDailyReportResponse,
    AgentHealthResponse,
    AgentMarketSentimentResponse,
    AgentNotificationTestRequest,
    AgentNotificationTestResponse,
    AgentPaperOrderRequest,
    AgentPaperOrderResponse,
    AgentSignalNotificationRequest,
    AgentSignalNotificationResponse,
    AgentSignalNotificationScanRequest,
    AgentSignalNotificationScanResponse,
    AgentOrderRecommendationRequest,
    AgentOrderRecommendationResponse,
    AgentPaperPortfolioResponse,
    AgentPositionTSignalRequest,
    AgentPositionTSignalResponse,
    AgentPriorityBoardResponse,
    AgentProviderStatusResponse,
    AgentResearchWorkflowRunRequest,
    AgentResearchWorkflowStatusResponse,
    AgentRiskCheckRequest,
    AgentSectorHeatmapResponse,
    AgentToolInvokeRequest,
    AgentToolResult,
    AgentWatchlistContextResponse,
)
from app.services.agent_context_service import AgentContextService
from app.services.agent_daily_workflow_service import AgentDailyWorkflowService
from app.services.agent_notification_service import AgentNotificationService
from app.services.agent_research_service import AgentResearchService
from app.services.agent_report_service import AgentReportService
from app.services.agent_signal_scan_service import AgentSignalScanService
from app.services.agent_workflow_job_service import AgentWorkflowJobService
from app.services.market_data import MarketDataService

router = APIRouter(prefix="/agent", dependencies=[Depends(require_current_user_or_agent_token)])

context_service = AgentContextService()
report_service = AgentReportService()
research_service = AgentResearchService(context_service=context_service)
market_data = MarketDataService()


@router.get("/health", response_model=AgentHealthResponse)
def agent_health(
    _: Optional[User] = Depends(require_agent_tool_permission("get_agent_health", "read")),
    db: Session = Depends(get_db),
) -> AgentHealthResponse:
    return context_service.health(db)


@router.get("/context/watchlist", response_model=AgentWatchlistContextResponse)
def agent_watchlist_context(
    _: Optional[User] = Depends(require_agent_tool_permission("get_watchlist_context", "read")),
    db: Session = Depends(get_db),
) -> AgentWatchlistContextResponse:
    return context_service.watchlist_context(db)


@router.get("/context/priority-board", response_model=AgentPriorityBoardResponse)
def agent_priority_board(
    limit: int = Query(default=12, ge=1, le=50),
    _: Optional[User] = Depends(require_agent_tool_permission("get_priority_board", "read")),
    db: Session = Depends(get_db),
) -> AgentPriorityBoardResponse:
    return context_service.priority_board(db, limit=limit)


@router.post("/context/analysis", response_model=AgentAnalysisResponse)
def agent_analysis(
    payload: AgentAnalysisRequest,
    _: Optional[User] = Depends(require_agent_tool_permission("analyze_stock", "read")),
    db: Session = Depends(get_db),
) -> AgentAnalysisResponse:
    return context_service.analysis(db, payload)


@router.get("/context/paper-portfolio", response_model=AgentPaperPortfolioResponse)
def agent_paper_portfolio(
    account_id: Optional[int] = Query(default=None),
    current_user: Optional[User] = Depends(require_agent_tool_permission("get_paper_portfolio", "read")),
    db: Session = Depends(get_db),
) -> AgentPaperPortfolioResponse:
    return context_service.paper_portfolio(db, account_id=account_id, user_id=getattr(current_user, "id", None))


@router.post("/context/recommend-orders", response_model=AgentOrderRecommendationResponse)
def agent_recommend_orders(
    payload: AgentOrderRecommendationRequest,
    current_user: Optional[User] = Depends(require_agent_tool_permission("recommend_orders", "write")),
    db: Session = Depends(get_db),
) -> AgentOrderRecommendationResponse:
    return context_service.recommend_orders(db, payload, user_id=getattr(current_user, "id", None))


@router.get("/reports/daily", response_model=AgentDailyReportResponse)
def agent_daily_report(
    _: Optional[User] = Depends(require_agent_tool_permission("get_daily_report", "read")),
    db: Session = Depends(get_db),
) -> AgentDailyReportResponse:
    return report_service.daily_report(db)


@router.post("/reports/daily/push", response_model=AgentDailyReportPushResponse)
def agent_daily_report_push(
    payload: AgentDailyReportPushRequest,
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> AgentDailyReportPushResponse:
    return AgentDailyWorkflowService().push_daily_report(db, channel=payload.channel)


@router.post("/workflows/tquant-daily-research/run", response_model=AgentResearchWorkflowStatusResponse)
def agent_tquant_daily_research_run(
    payload: AgentResearchWorkflowRunRequest,
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> AgentResearchWorkflowStatusResponse:
    job = AgentWorkflowJobService().start_daily_research(
        db,
        open_id=payload.open_id,
        symbols=payload.symbols,
        channel=payload.channel,
    )
    return AgentResearchWorkflowStatusResponse(**job.__dict__)


@router.get("/workflows/tquant-daily-research/latest", response_model=AgentResearchWorkflowStatusResponse)
def agent_tquant_daily_research_latest(
    open_id: str = Query(default=""),
    channel: str = Query(default="feishu"),
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> AgentResearchWorkflowStatusResponse:
    job = AgentWorkflowJobService().latest_daily_research(db, open_id=open_id, channel=channel)
    return AgentResearchWorkflowStatusResponse(**job.__dict__)


@router.post("/notify/test", response_model=AgentNotificationTestResponse)
def agent_notify_test(
    payload: AgentNotificationTestRequest,
    _: Optional[User] = Depends(require_agent_tool_permission("send_test_notification", "notify")),
) -> AgentNotificationTestResponse:
    return AgentNotificationService().send_test(payload)


@router.post("/notify/signal", response_model=AgentSignalNotificationResponse)
def agent_notify_signal(
    payload: AgentSignalNotificationRequest,
    current_user: Optional[User] = Depends(require_agent_tool_permission("send_signal_notification", "notify")),
    db: Session = Depends(get_db),
) -> AgentSignalNotificationResponse:
    return AgentNotificationService().send_signal(
        db,
        payload,
        user_id=getattr(current_user, "id", None),
    )


@router.post("/notify/scan-priority-board", response_model=AgentSignalNotificationScanResponse)
def agent_notify_scan_priority_board(
    payload: AgentSignalNotificationScanRequest,
    current_user: Optional[User] = Depends(require_agent_tool_permission("scan_priority_board_notifications", "notify")),
    db: Session = Depends(get_db),
) -> AgentSignalNotificationScanResponse:
    return AgentSignalScanService().scan_priority_board(
        db,
        limit=payload.limit,
        channel=payload.channel,
        user_id=getattr(current_user, "id", None),
    )


@router.post("/context/backtest", response_model=AgentBacktestResponse)
def agent_backtest_strategy(
    payload: AgentBacktestRequest,
    _: Optional[User] = Depends(require_agent_tool_permission("backtest_strategy", "read")),
    db: Session = Depends(get_db),
) -> AgentBacktestResponse:
    return run_agent_backtest_strategy(context_service, db, payload)


@router.post("/context/compare-strategies", response_model=AgentCompareStrategiesResponse)
def agent_compare_strategies(
    payload: AgentCompareStrategiesRequest,
    _: Optional[User] = Depends(require_agent_tool_permission("compare_strategies", "read")),
    db: Session = Depends(get_db),
) -> AgentCompareStrategiesResponse:
    return run_agent_compare_strategies(
        context_service,
        db,
        strategy_keys=payload.strategy_keys,
        lookback_days=payload.lookback_days,
    )


@router.post("/paper/order", response_model=AgentPaperOrderResponse)
def agent_create_paper_order(
    payload: AgentPaperOrderRequest,
    current_user: Optional[User] = Depends(require_agent_tool_permission("create_paper_order", "write")),
    db: Session = Depends(get_db),
) -> AgentPaperOrderResponse:
    return run_agent_create_paper_order(context_service, db, payload, user_id=getattr(current_user, "id", None))


@router.get("/context/market-sentiment", response_model=AgentMarketSentimentResponse)
def agent_market_sentiment(
    _: Optional[User] = Depends(require_agent_tool_permission("get_market_sentiment", "read")),
) -> AgentMarketSentimentResponse:
    return run_agent_market_sentiment(context_service, market_data)


@router.get("/context/sector-heatmap", response_model=AgentSectorHeatmapResponse)
def agent_sector_heatmap(
    limit: int = Query(default=20, ge=5, le=50),
    _: Optional[User] = Depends(require_agent_tool_permission("get_sector_heatmap", "read")),
) -> AgentSectorHeatmapResponse:
    return run_agent_sector_heatmap(context_service, market_data, limit=limit)


@router.post("/context/position-t-signal", response_model=AgentPositionTSignalResponse)
def agent_position_t_signal(
    payload: AgentPositionTSignalRequest,
    _: Optional[User] = Depends(require_agent_tool_permission("get_position_t_signal", "read")),
    db: Session = Depends(get_db),
) -> AgentPositionTSignalResponse:
    return run_agent_position_t_signal(context_service, db, payload)


@router.get("/context/market-state-analysis")
def agent_market_state_analysis(
    _: Optional[User] = Depends(require_agent_tool_permission("get_market_state_analysis", "read")),
    db: Session = Depends(get_db),
) -> dict:
    return research_service.market_state_analysis(db)


@router.get("/context/sector-mainline-analysis")
def agent_sector_mainline_analysis(
    _: Optional[User] = Depends(require_agent_tool_permission("get_sector_mainline_analysis", "read")),
    db: Session = Depends(get_db),
) -> dict:
    return research_service.sector_mainline_analysis(db)


@router.post("/context/strategy-cross-validation")
def agent_strategy_cross_validation(
    payload: AgentCrossValidationRequest,
    _: Optional[User] = Depends(require_agent_tool_permission("cross_validate_strategy_context", "read")),
    db: Session = Depends(get_db),
) -> dict:
    return research_service.cross_validate(db, payload.symbols)


@router.post("/context/risk-check")
def agent_risk_check(
    payload: AgentRiskCheckRequest,
    _: Optional[User] = Depends(require_agent_tool_permission("check_agent_risk", "read")),
    db: Session = Depends(get_db),
) -> dict:
    return research_service.risk_check(db, payload.proposals)


@router.post("/context/comprehensive-analysis")
def agent_comprehensive_analysis(
    payload: AgentComprehensiveAnalysisRequest,
    _: Optional[User] = Depends(require_agent_tool_permission("get_comprehensive_analysis", "read")),
    db: Session = Depends(get_db),
) -> dict:
    return research_service.comprehensive_analysis(db, payload.symbols)


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


@router.get("/audit/summary", response_model=AgentAuditSummaryResponse)
def agent_audit_logs_summary(
    agent_id: Optional[str] = Query(default=None),
    recent_limit: int = Query(default=100, ge=1, le=1000),
    top_limit: int = Query(default=10, ge=1, le=50),
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> AgentAuditSummaryResponse:
    return AgentAuditSummaryResponse(
        **agent_audit_summary(
            db,
            agent_id=agent_id,
            recent_limit=recent_limit,
            top_limit=top_limit,
        )
    )


@router.get("/audit", response_model=list[AgentAuditLogOut])
def agent_audit_logs(
    agent_id: Optional[str] = Query(default=None),
    tool: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    _: None = Depends(require_admin_auth),
    db: Session = Depends(get_db),
) -> list[AgentAuditLogOut]:
    statement = select(AgentAuditLog).order_by(AgentAuditLog.id.desc()).limit(limit)
    if tool:
        statement = statement.where(AgentAuditLog.tool_name == tool)
    rows = db.execute(statement).scalars().all()
    output = [audit_log_out(row) for row in rows]
    if agent_id:
        output = [row for row in output if row.agent_id == agent_id]
    return output
