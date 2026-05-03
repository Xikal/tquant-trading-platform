from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agent_tools.schemas import ToolDefinition
from app.models.schema_defs.agent import (
    AgentAnalysisRequest,
    AgentNotificationTestRequest,
    AgentOrderRecommendationRequest,
    AgentSignalNotificationRequest,
)
from app.services.agent_context_service import AgentContextService
from app.services.agent_notification_service import AgentNotificationService
from app.services.agent_report_service import AgentReportService
from app.services.agent_signal_scan_service import AgentSignalScanService


class LocalSafeApiInvoker:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.context = AgentContextService()
        self.reports = AgentReportService()
        self.notifications = AgentNotificationService()

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
        raise ValueError(f"Unsupported local tool: {tool.name}")
