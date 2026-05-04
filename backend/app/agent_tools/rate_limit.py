from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.agent_tools.schemas import ToolDefinition


_DEFAULT_LIMITS_PER_MINUTE: dict[str, int] = {
    "get_agent_health": 60,
    "get_watchlist_context": 30,
    "get_priority_board": 20,
    "analyze_stock": 12,
    "get_daily_report": 12,
    "get_paper_portfolio": 20,
    "recommend_orders": 6,
    "send_test_notification": 3,
    "send_signal_notification": 10,
    "scan_priority_board_notifications": 4,
    "backtest_strategy": 4,
    "compare_strategies": 4,
    "create_paper_order": 6,
    "get_market_sentiment": 20,
    "get_sector_heatmap": 20,
    "get_position_t_signal": 12,
    "get_market_state_analysis": 20,
    "get_sector_mainline_analysis": 20,
    "cross_validate_strategy_context": 10,
    "check_agent_risk": 20,
    "get_comprehensive_analysis": 8,
}


class AgentToolRateLimiter:
    """Small in-process limiter for agent tool invocation.

    This protects the web process from accidental tight loops. It is deliberately
    conservative and provider-agnostic; external distributed limiting can be
    added later without changing provider call sites.
    """

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, provider_name: str, tool: ToolDefinition) -> tuple[bool, int]:
        limit = _DEFAULT_LIMITS_PER_MINUTE.get(tool.name, 20)
        key = f"{provider_name}:{tool.name}"
        now = time.monotonic()
        window_start = now - 60
        with self._lock:
            events = self._events[key]
            while events and events[0] < window_start:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, int(60 - (now - events[0])))
                return False, retry_after
            events.append(now)
            return True, 0


agent_tool_rate_limiter = AgentToolRateLimiter()
