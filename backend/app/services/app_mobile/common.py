from __future__ import annotations

from typing import Iterable, Optional

from app.core.timezone import beijing_now


def now_string() -> str:
    return beijing_now().strftime("%Y-%m-%d %H:%M:%S")


def dedupe_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def headline_reason(signal: dict) -> str:
    reasons = list(signal.get("reasons") or [])
    if reasons:
        return str(reasons[0])
    strategy_notes = str(signal.get("strategy_notes") or "").strip()
    if strategy_notes:
        return strategy_notes
    return "等待新的盘中条件触发。"


def headline_blocker(signal: dict) -> str:
    blocking_rules = list(signal.get("blocking_rules") or [])
    return str(blocking_rules[0]) if blocking_rules else ""


def derive_stale_flag(error: Optional[str], quote_timestamp: Optional[str]) -> bool:
    if error:
        return True
    return not bool((quote_timestamp or "").strip())


def collect_warning_messages(items: Iterable[Optional[str]]) -> list[str]:
    return dedupe_preserve_order(item for item in items if item)
