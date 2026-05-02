from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agent_tools.schemas import ToolDefinition
from app.models.schema_defs.agent import AgentAnalysisRequest, AgentNotificationTestRequest
from app.services.agent_context_service import AgentContextService
from app.services.agent_report_service import AgentReportService


class LocalSafeApiInvoker:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.context = AgentContextService()
        self.reports = AgentReportService()

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
        if tool.name == "send_test_notification":
            payload = AgentNotificationTestRequest.model_validate(arguments or {})
            return {
                "ok": True,
                "channel": payload.channel,
                "message": "notification adapter not configured",
            }
        raise ValueError(f"Unsupported local tool: {tool.name}")
