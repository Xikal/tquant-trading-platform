from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.api.routes.agent_helpers import (
    agent_backtest_strategy,
    agent_compare_strategies,
    agent_create_paper_order,
    agent_market_sentiment,
    agent_position_t_signal,
    agent_sector_heatmap,
)
from app.agent_tools.schemas import ToolDefinition
from app.models.schema_defs.agent import (
    AgentAnalysisRequest,
    AgentBacktestRequest,
    AgentCompareStrategiesRequest,
    AgentComprehensiveAnalysisRequest,
    AgentCrossValidationRequest,
    AgentNotificationTestRequest,
    AgentOrderRecommendationRequest,
    AgentPaperOrderRequest,
    AgentPositionTSignalRequest,
    AgentRiskCheckRequest,
    AgentSignalNotificationRequest,
)
from app.models.schema_defs.agent_platform import AgentPlatformAutopilotRunRequest
from app.services.agent_context_service import AgentContextService
from app.services.agent_notification_service import AgentNotificationService
from app.services.agent_research_service import AgentResearchService
from app.services.agent_report_service import AgentReportService
from app.services.agent_signal_scan_service import AgentSignalScanService
from app.services.market_data import MarketDataService
from app.services.platform_autopilot import PlatformAutopilotService


class LocalSafeApiInvoker:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.context = AgentContextService()
        self.reports = AgentReportService()
        self.research = AgentResearchService(db, context_service=self.context)
        self.notifications = AgentNotificationService()
        self.market_data = MarketDataService()

    def invoke(self, tool: ToolDefinition, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool.name == "get_agent_health":
            return self.context.health(self.db).model_dump()
        if tool.name == "get_watchlist_context":
            return self.context.watchlist_context(self.db).model_dump()
        if tool.name == "get_priority_board":
            return self.context.priority_board(self.db, limit=int(arguments.get("limit", 12))).model_dump()
        if tool.name == "analyze_stock":
            return self.context.analysis(self.db, AgentAnalysisRequest.model_validate(arguments)).model_dump()
        if tool.name == "get_daily_report":
            return self.reports.daily_report(self.db).model_dump()
        if tool.name == "get_paper_portfolio":
            account_id = arguments.get("account_id")
            return self.context.paper_portfolio(self.db, int(account_id) if account_id else None, user_id=None).model_dump()
        if tool.name == "recommend_orders":
            return self.context.recommend_orders(
                self.db,
                AgentOrderRecommendationRequest.model_validate(arguments or {}),
                user_id=None,
            ).model_dump()
        if tool.name == "send_test_notification":
            payload = AgentNotificationTestRequest.model_validate(arguments or {})
            return self.notifications.send_test(payload).model_dump()
        if tool.name == "get_platform_autopilot_status":
            return PlatformAutopilotService(self.db).run(
                auto_repair=False,
                notify=False,
                audit=False,
                trigger="local_provider_status",
            ).model_dump(mode="json")
        if tool.name == "run_platform_autopilot":
            payload = AgentPlatformAutopilotRunRequest.model_validate(arguments or {})
            return PlatformAutopilotService(self.db).run(
                auto_repair=payload.auto_repair,
                notify=payload.notify,
                trigger=payload.trigger or "local_provider",
            ).model_dump(mode="json")
        if tool.name == "send_signal_notification":
            payload = AgentSignalNotificationRequest.model_validate(arguments or {})
            return self.notifications.send_signal(self.db, payload, user_id=None).model_dump()
        if tool.name == "scan_priority_board_notifications":
            return AgentSignalScanService(self.notifications).scan_priority_board(
                self.db,
                limit=int(arguments.get("limit", 12)),
                channel=str(arguments.get("channel") or "feishu"),
                user_id=None,
            ).model_dump()
        if tool.name == "backtest_strategy":
            payload = AgentBacktestRequest.model_validate(arguments or {})
            return agent_backtest_strategy(self.context, self.db, payload).model_dump()
        if tool.name == "compare_strategies":
            payload = AgentCompareStrategiesRequest.model_validate(arguments or {})
            return agent_compare_strategies(
                self.context,
                self.db,
                strategy_keys=payload.strategy_keys,
                lookback_days=payload.lookback_days,
            ).model_dump()
        if tool.name == "create_paper_order":
            payload = AgentPaperOrderRequest.model_validate(arguments or {})
            return agent_create_paper_order(self.context, self.db, payload, user_id=None).model_dump()
        if tool.name == "get_market_sentiment":
            return agent_market_sentiment(self.context, self.market_data).model_dump()
        if tool.name == "get_sector_heatmap":
            return agent_sector_heatmap(self.context, self.market_data, limit=int(arguments.get("limit", 20))).model_dump()
        if tool.name == "get_position_t_signal":
            payload = AgentPositionTSignalRequest.model_validate(arguments or {})
            return agent_position_t_signal(self.context, self.db, payload).model_dump()
        if tool.name == "get_market_state_analysis":
            return self.research.market_state_analysis(self.db)
        if tool.name == "get_sector_mainline_analysis":
            return self.research.sector_mainline_analysis(self.db)
        if tool.name == "cross_validate_strategy_context":
            payload = AgentCrossValidationRequest.model_validate(arguments or {})
            return self.research.cross_validate(self.db, payload.symbols)
        if tool.name == "check_agent_risk":
            payload = AgentRiskCheckRequest.model_validate(arguments or {})
            return self.research.risk_check(self.db, payload.proposals)
        if tool.name == "get_comprehensive_analysis":
            payload = AgentComprehensiveAnalysisRequest.model_validate(arguments or {})
            return self.research.comprehensive_analysis(self.db, payload.symbols)
        raise ValueError(f"Unsupported local tool: {tool.name}")
