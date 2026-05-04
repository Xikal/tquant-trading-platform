from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PaperExitReason(str, Enum):
    TAKE_PROFIT = "take_profit"
    PARTIAL_TAKE_PROFIT = "partial_take_profit"
    STOP_LOSS = "stop_loss"
    TRAILING_STOP = "trailing_stop"
    TIME_STOP = "time_stop"
    RISK_CONTROL = "risk_control"
    SIGNAL_INVALID = "signal_invalid"
    AUTO_REBALANCE = "auto_rebalance"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class PaperEntryReason(str, Enum):
    STRATEGY_SIGNAL = "strategy_signal"
    LOW_BUY_SIGNAL = "low_buy_signal"
    POSITIVE_T = "positive_t"
    WEAK_TO_STRONG = "weak_to_strong"
    AUTO_ENTRY = "auto_entry"
    MANUAL_ENTRY = "manual_entry"
    UNKNOWN = "unknown"


EXIT_REASON_TEXT: dict[PaperExitReason, str] = {
    PaperExitReason.TAKE_PROFIT: "止盈退出",
    PaperExitReason.PARTIAL_TAKE_PROFIT: "分批止盈",
    PaperExitReason.STOP_LOSS: "止损退出",
    PaperExitReason.TRAILING_STOP: "移动止盈退出",
    PaperExitReason.TIME_STOP: "时间退出",
    PaperExitReason.RISK_CONTROL: "风控退出",
    PaperExitReason.SIGNAL_INVALID: "信号失效退出",
    PaperExitReason.AUTO_REBALANCE: "自动调仓",
    PaperExitReason.MANUAL: "手动退出",
    PaperExitReason.UNKNOWN: "退出原因未标注",
}


ENTRY_REASON_TEXT: dict[PaperEntryReason, str] = {
    PaperEntryReason.STRATEGY_SIGNAL: "策略信号买入",
    PaperEntryReason.LOW_BUY_SIGNAL: "低吸信号买入",
    PaperEntryReason.POSITIVE_T: "正T低吸买入",
    PaperEntryReason.WEAK_TO_STRONG: "弱转强确认买入",
    PaperEntryReason.AUTO_ENTRY: "自动交易信号买入",
    PaperEntryReason.MANUAL_ENTRY: "手动录入买入",
    PaperEntryReason.UNKNOWN: "买入原因未标注",
}


@dataclass(frozen=True)
class StandardReason:
    code: str
    text: str


def normalize_exit_reason(raw: str | None, *, source: str = "") -> StandardReason:
    value = (raw or "").strip()
    lowered = value.lower()
    if "分批" in value or "减仓" in value or "partial" in lowered:
        return _exit_reason(PaperExitReason.PARTIAL_TAKE_PROFIT)
    if "移动" in value or "回落保护" in value or "trailing" in lowered:
        return _exit_reason(PaperExitReason.TRAILING_STOP)
    if "止盈" in value or "冲高" in value or "take_profit" in lowered:
        return _exit_reason(PaperExitReason.TAKE_PROFIT)
    if "止损" in value or "跌破" in value or "stop" in lowered:
        return _exit_reason(PaperExitReason.STOP_LOSS)
    if "最长持有" in value or "时间" in value or "time" in lowered:
        return _exit_reason(PaperExitReason.TIME_STOP)
    if "风控" in value or "熔断" in value or "risk" in lowered:
        return _exit_reason(PaperExitReason.RISK_CONTROL)
    if "失效" in value or "确认失败" in value or "invalid" in lowered:
        return _exit_reason(PaperExitReason.SIGNAL_INVALID)
    if "auto" in source or "自动" in value:
        return _exit_reason(PaperExitReason.AUTO_REBALANCE)
    if value:
        return StandardReason(code=PaperExitReason.MANUAL.value, text=value[:80])
    return _exit_reason(PaperExitReason.UNKNOWN)


def normalize_entry_reason(raw: str | None, *, source: str = "") -> StandardReason:
    value = (raw or "").strip()
    lowered = value.lower()
    if "正t" in value.lower() or "positive_t" in lowered:
        return _entry_reason(PaperEntryReason.POSITIVE_T)
    if "弱转强" in value or "weak" in lowered:
        return _entry_reason(PaperEntryReason.WEAK_TO_STRONG)
    if "低吸" in value or "low_buy" in lowered:
        return _entry_reason(PaperEntryReason.LOW_BUY_SIGNAL)
    if "策略" in value or "signal" in lowered:
        return _entry_reason(PaperEntryReason.STRATEGY_SIGNAL)
    if value:
        return StandardReason(code=PaperEntryReason.MANUAL_ENTRY.value, text=value[:120])
    if "auto" in source:
        return _entry_reason(PaperEntryReason.AUTO_ENTRY)
    return _entry_reason(PaperEntryReason.MANUAL_ENTRY)


def _exit_reason(reason: PaperExitReason) -> StandardReason:
    return StandardReason(code=reason.value, text=EXIT_REASON_TEXT[reason])


def _entry_reason(reason: PaperEntryReason) -> StandardReason:
    return StandardReason(code=reason.value, text=ENTRY_REASON_TEXT[reason])
