from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PaperExitReason(str, Enum):
    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    TIME_STOP = "time_stop"
    RISK_CONTROL = "risk_control"
    AUTO_REBALANCE = "auto_rebalance"
    MANUAL = "manual"
    UNKNOWN = "unknown"


EXIT_REASON_TEXT: dict[PaperExitReason, str] = {
    PaperExitReason.TAKE_PROFIT: "止盈退出",
    PaperExitReason.STOP_LOSS: "止损退出",
    PaperExitReason.TIME_STOP: "时间退出",
    PaperExitReason.RISK_CONTROL: "风控退出",
    PaperExitReason.AUTO_REBALANCE: "自动调仓",
    PaperExitReason.MANUAL: "手动退出",
    PaperExitReason.UNKNOWN: "退出原因未标注",
}


@dataclass(frozen=True)
class StandardReason:
    code: str
    text: str


def normalize_exit_reason(raw: str | None, *, source: str = "") -> StandardReason:
    value = (raw or "").strip()
    lowered = value.lower()
    if "止盈" in value or "冲高" in value or "take_profit" in lowered:
        return _reason(PaperExitReason.TAKE_PROFIT)
    if "止损" in value or "跌破" in value or "stop" in lowered:
        return _reason(PaperExitReason.STOP_LOSS)
    if "最长持有" in value or "时间" in value or "time" in lowered:
        return _reason(PaperExitReason.TIME_STOP)
    if "风控" in value or "熔断" in value or "risk" in lowered:
        return _reason(PaperExitReason.RISK_CONTROL)
    if "auto" in source or "自动" in value:
        return _reason(PaperExitReason.AUTO_REBALANCE)
    if value:
        return StandardReason(code=PaperExitReason.MANUAL.value, text=value[:80])
    return _reason(PaperExitReason.UNKNOWN)


def normalize_entry_reason(raw: str | None, *, source: str = "") -> StandardReason:
    value = (raw or "").strip()
    if value:
        return StandardReason(code="planned_entry", text=value[:120])
    if "auto" in source:
        return StandardReason(code="auto_entry", text="自动交易信号买入")
    return StandardReason(code="manual_entry", text="手动录入买入")


def _reason(reason: PaperExitReason) -> StandardReason:
    return StandardReason(code=reason.value, text=EXIT_REASON_TEXT[reason])
