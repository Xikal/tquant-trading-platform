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
            capabilities=("health_read",),
            timeout_seconds=timeout,
        ),
        ToolDefinition(
            name="get_watchlist_context",
            description="获取自选和持仓监控摘要",
            method="GET",
            path="/api/agent/context/watchlist",
            input_schema={"type": "object", "properties": {}},
            permission="read",
            capabilities=("watchlist_read",),
            timeout_seconds=timeout,
        ),
        ToolDefinition(
            name="get_priority_board",
            description="获取生产优先榜摘要",
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
            capabilities=("priority_board_read", "strategy_signal_read"),
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
            capabilities=("analysis_read",),
            timeout_seconds=timeout,
        ),
        ToolDefinition(
            name="get_daily_report",
            description="生成规则化每日复盘报告",
            method="GET",
            path="/api/agent/reports/daily",
            input_schema={"type": "object", "properties": {}},
            permission="read",
            capabilities=("daily_report_read",),
            timeout_seconds=timeout,
        ),
        ToolDefinition(
            name="get_paper_portfolio",
            description="获取模拟盘账户、持仓和绩效摘要",
            method="GET",
            path="/api/agent/context/paper-portfolio",
            input_schema={
                "type": "object",
                "properties": {
                    "account_id": {"type": ["integer", "null"]},
                },
            },
            permission="read",
            capabilities=("paper_portfolio_read",),
            timeout_seconds=timeout,
        ),
        ToolDefinition(
            name="recommend_orders",
            description="基于优先级榜生成模拟委托建议，不执行下单",
            method="POST",
            path="/api/agent/context/recommend-orders",
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 12, "minimum": 1, "maximum": 50},
                    "account_id": {"type": ["integer", "null"]},
                },
            },
            permission="write",
            capabilities=("paper_order_recommend",),
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
            capabilities=("notification_test",),
            timeout_seconds=timeout,
        ),
        ToolDefinition(
            name="get_platform_autopilot_status",
            description="获取平台自动巡检状态，只读检查，不执行修复动作",
            method="GET",
            path="/api/agent/platform/autopilot/latest",
            input_schema={"type": "object", "properties": {}},
            permission="read",
            capabilities=("platform_autopilot_read",),
            timeout_seconds=timeout,
        ),
        ToolDefinition(
            name="run_platform_autopilot",
            description="执行白名单平台自动巡检和低风险自愈动作，不部署、不删库、不改策略、不恢复交易",
            method="POST",
            path="/api/agent/platform/autopilot/run",
            input_schema={
                "type": "object",
                "properties": {
                    "auto_repair": {"type": "boolean", "default": True},
                    "notify": {"type": "boolean", "default": True},
                    "trigger": {"type": "string", "default": "agent"},
                },
            },
            permission="write",
            capabilities=("platform_autopilot_run",),
            timeout_seconds=max(timeout, 30),
        ),
        ToolDefinition(
            name="send_signal_notification",
            description="按股票、策略和信号状态发送去重后的通知；信号升级会立即通知",
            method="POST",
            path="/api/agent/notify/signal",
            input_schema={
                "type": "object",
                "required": ["symbol", "signal_state"],
                "properties": {
                    "channel": {"type": "string", "default": "feishu"},
                    "symbol": {"type": "string"},
                    "name": {"type": "string", "default": ""},
                    "strategy_key": {"type": "string", "default": ""},
                    "strategy_title": {"type": "string", "default": ""},
                    "signal_state": {"type": "string"},
                    "signal_text": {"type": "string", "default": ""},
                    "message": {"type": "string", "default": ""},
                    "event_type": {"type": "string", "default": "signal"},
                    "payload": {"type": "object", "default": {}},
                },
            },
            permission="notify",
            capabilities=("signal_notification_send",),
            timeout_seconds=timeout,
        ),
        ToolDefinition(
            name="scan_priority_board_notifications",
            description="扫描生产优先榜并按通知账本发送新增或升级信号",
            method="POST",
            path="/api/agent/notify/scan-priority-board",
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 12, "minimum": 1, "maximum": 50},
                    "channel": {"type": "string", "default": "feishu"},
                },
            },
            permission="notify",
            capabilities=("signal_notification_scan",),
            timeout_seconds=timeout,
        ),
        ToolDefinition(
            name="backtest_strategy",
            description="对指定策略执行指定周期的回测，返回绩效摘要",
            method="POST",
            path="/api/agent/context/backtest",
            input_schema={
                "type": "object",
                "required": ["strategy_key"],
                "properties": {
                    "strategy_key": {"type": "string"},
                    "lookback_days": {"type": "integer", "default": 60, "minimum": 20, "maximum": 250},
                },
            },
            permission="read",
            capabilities=("strategy_backtest_read",),
            timeout_seconds=60,
        ),
        ToolDefinition(
            name="compare_strategies",
            description="对比多个策略在相同周期内的绩效差异",
            method="POST",
            path="/api/agent/context/compare-strategies",
            input_schema={
                "type": "object",
                "required": ["strategy_keys"],
                "properties": {
                    "strategy_keys": {"type": "array", "items": {"type": "string"}},
                    "lookback_days": {"type": "integer", "default": 60, "minimum": 20, "maximum": 250},
                },
            },
            permission="read",
            capabilities=("strategy_compare_read",),
            timeout_seconds=90,
        ),
        ToolDefinition(
            name="create_paper_order",
            description="创建模拟盘订单（不执行实盘交易）",
            method="POST",
            path="/api/agent/paper/order",
            input_schema={
                "type": "object",
                "required": ["symbol", "side", "quantity", "price"],
                "properties": {
                    "symbol": {"type": "string"},
                    "side": {"type": "string", "enum": ["buy", "sell"]},
                    "quantity": {"type": "integer", "minimum": 100, "maximum": 1000000},
                    "price": {"type": "number", "minimum": 0.01},
                    "account_id": {"type": ["integer", "null"]},
                },
            },
            permission="write",
            capabilities=("paper_order_create",),
            timeout_seconds=30,
        ),
        ToolDefinition(
            name="get_market_sentiment",
            description="获取市场情绪摘要：涨停/跌停数、炸板率、连板高度、资金流向",
            method="GET",
            path="/api/agent/context/market-sentiment",
            input_schema={"type": "object", "properties": {}},
            permission="read",
            capabilities=("market_sentiment_read",),
            timeout_seconds=15,
        ),
        ToolDefinition(
            name="get_sector_heatmap",
            description="获取板块涨跌幅排行、资金流向、涨停数分布",
            method="GET",
            path="/api/agent/context/sector-heatmap",
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 20, "minimum": 5, "maximum": 50},
                },
            },
            permission="read",
            capabilities=("sector_heatmap_read",),
            timeout_seconds=15,
        ),
        ToolDefinition(
            name="get_sector_fund_flow",
            description="获取板块主力资金净流入排行（今日/5日/10日，行业/概念/地域），数据来自东方财富数据中心",
            method="GET",
            path="/api/agent/context/sector-fund-flow",
            input_schema={
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "default": "today",
                        "enum": ["today", "5day", "10day"],
                        "description": "时间周期：today=今日, 5day=5日, 10day=10日",
                    },
                    "sector_type": {
                        "type": "string",
                        "default": "industry",
                        "enum": ["industry", "concept", "region"],
                        "description": "板块类型：industry=行业, concept=概念, region=地域",
                    },
                    "limit": {"type": "integer", "default": 30, "minimum": 5, "maximum": 100},
                },
            },
            permission="read",
            capabilities=("sector_fund_flow_read",),
            timeout_seconds=15,
        ),
        ToolDefinition(
            name="get_position_t_signal",
            description="获取指定持仓的正T/反T信号和建议操作",
            method="POST",
            path="/api/agent/context/position-t-signal",
            input_schema={
                "type": "object",
                "required": ["symbol"],
                "properties": {
                    "symbol": {"type": "string"},
                    "shares": {"type": "integer"},
                    "cost_basis": {"type": "number"},
                },
            },
            permission="read",
            capabilities=("position_t_signal_read",),
            timeout_seconds=15,
        ),
        ToolDefinition(
            name="get_market_state_analysis",
            description="获取市场状态、情绪、广度和仓位边界的只读研究上下文",
            method="GET",
            path="/api/agent/context/market-state-analysis",
            input_schema={"type": "object", "properties": {}},
            permission="read",
            capabilities=("market_state_research_read",),
            timeout_seconds=15,
        ),
        ToolDefinition(
            name="get_sector_mainline_analysis",
            description="获取板块主线、轮动风险和核心候选的只读研究上下文",
            method="GET",
            path="/api/agent/context/sector-mainline-analysis",
            input_schema={"type": "object", "properties": {}},
            permission="read",
            capabilities=("sector_mainline_research_read",),
            timeout_seconds=15,
        ),
        ToolDefinition(
            name="cross_validate_strategy_context",
            description="交叉验证指定股票在优先级榜、个股分析和市场主线中的一致性",
            method="POST",
            path="/api/agent/context/strategy-cross-validation",
            input_schema={
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                        "maxItems": 30,
                    }
                },
            },
            permission="read",
            capabilities=("strategy_context_validate_read",),
            timeout_seconds=30,
        ),
        ToolDefinition(
            name="check_agent_risk",
            description="对候选计划做只读仓位、行业集中度和总仓位风险检查",
            method="POST",
            path="/api/agent/context/risk-check",
            input_schema={
                "type": "object",
                "properties": {
                    "proposals": {
                        "type": "array",
                        "items": {"type": "object"},
                        "default": [],
                        "maxItems": 50,
                    }
                },
            },
            permission="read",
            capabilities=("agent_risk_check_read",),
            timeout_seconds=15,
        ),
        ToolDefinition(
            name="get_comprehensive_analysis",
            description="整合市场、板块、个股交叉验证和风控检查，输出只读综合研判",
            method="POST",
            path="/api/agent/context/comprehensive-analysis",
            input_schema={
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                        "maxItems": 30,
                    }
                },
            },
            permission="read",
            capabilities=("comprehensive_research_read",),
            timeout_seconds=45,
        ),
    ]
    return {tool.name: tool for tool in tools}
