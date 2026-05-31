from __future__ import annotations

DEFAULT_LIMIT = 30
MAX_LIMIT = 50
DEFAULT_RANGE_DAYS = 30
MAX_TRACKING_DAYS = 20
MISSING_SIGNAL_GRACE_DAYS = 3
PROFIT_TARGET_PCT = 8.0

TRACKED_SIGNAL_STATES = ("buy_now", "soft_buy_now", "near_entry", "observe_confirmed")
PRIMARY_SIGNAL_STATES = ("buy_now", "soft_buy_now", "near_entry")

STATUS_LABELS = {
    "active": "仍在跟踪",
    "completed_profit": "达到止盈观察",
    "stopped": "跌破止损",
    "expired": "超过跟踪周期",
    "invalidated": "策略失效",
    "data_unavailable": "数据不足",
}

SIGNAL_LABELS = {
    "buy_now": "确定可买",
    "soft_buy_now": "小仓试买",
    "near_entry": "接近买点（观察）",
    "observe_confirmed": "观察确认（非买入）",
}
