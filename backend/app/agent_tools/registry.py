from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.agent_tools.schemas import ToolDefinition


def list_tool_definitions() -> list[ToolDefinition]:
    return list(_tool_registry().values())


def get_tool_definition(name: str) -> ToolDefinition | None:
    return _tool_registry().get(name)


def enabled_tool_definitions() -> list[ToolDefinition]:
    return [tool for tool in list_tool_definitions() if tool.enabled]


@lru_cache(maxsize=1)
def _tool_registry() -> dict[str, ToolDefinition]:
    timeout = max(int(get_settings().agent_timeout_seconds), 1)
    tools = [
        ToolDefinition(
            name="get_agent_health",
            description="获取项目与 Agent 能力层健康状态",
            method="GET",
            path="/api/agent/health",
            input_schema={"type": "object", "properties": {}},
            permission="read",
            timeout_seconds=timeout,
        ),
        ToolDefinition(
            name="get_watchlist_context",
            description="获取自选和持仓监控摘要",
            method="GET",
            path="/api/agent/context/watchlist",
            input_schema={"type": "object", "properties": {}},
            permission="read",
            timeout_seconds=timeout,
        ),
        ToolDefinition(
            name="get_priority_board",
            description="获取全策略优先级榜摘要",
            method="GET",
            path="/api/agent/context/priority-board",
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "default": 12,
                        "minimum": 1,
                        "maximum": 50,
                    }
                },
            },
            permission="read",
            timeout_seconds=timeout,
        ),
        ToolDefinition(
            name="analyze_stock",
            description="分析单只股票的做T条件摘要",
            method="POST",
            path="/api/agent/context/analysis",
            input_schema={
                "type": "object",
                "required": ["symbol"],
                "properties": {
                    "symbol": {"type": "string"},
                    "base_position": {"type": "integer", "default": 1000},
                    "available_position": {"type": "integer", "default": 1000},
                    "cost_basis": {"type": ["number", "null"]},
                    "include_ai": {"type": "boolean", "default": False},
                },
            },
            permission="read",
            timeout_seconds=timeout,
        ),
        ToolDefinition(
            name="get_daily_report",
            description="生成规则化每日复盘报告",
            method="GET",
            path="/api/agent/reports/daily",
            input_schema={"type": "object", "properties": {}},
            permission="read",
            timeout_seconds=timeout,
        ),
        ToolDefinition(
            name="send_test_notification",
            description="测试通知通道是否可用",
            method="POST",
            path="/api/agent/notify/test",
            input_schema={
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "default": "feishu"},
                    "message": {"type": "string", "default": "测试消息"},
                },
            },
            permission="notify",
            timeout_seconds=timeout,
        ),
    ]
    return {tool.name: tool for tool in tools}
