from __future__ import annotations

from typing import Any

from app.services.low_buy.strategy_lanes import FRONT_ROW_ONLY_VARIANT
from app.services.low_buy.strategy_policy import participates_in_priority_board
from app.services.strategy_engine.gates import StrategyGateInput


def low_buy_strategy_gate_input(candidate: Any, *, strategy_variant: str = "baseline") -> StrategyGateInput:
    strategy_key = _text(candidate, "strategy_key")
    return StrategyGateInput(
        strategy_key=strategy_key,
        signal_state=_text(candidate, "buy_signal_state", "watch"),
        participates_in_priority_board=participates_in_priority_board(strategy_key),
        research_only=bool(getattr(candidate, "research_only", False)),
        watch_only=bool(getattr(candidate, "watch_only", False)),
        shadow_paper=bool(getattr(candidate, "paper_enabled", False)),
        front_row_only=str(strategy_variant or "") == FRONT_ROW_ONLY_VARIANT,
        blocked=_risk_blocked(candidate),
        reasons=_input_reasons(candidate),
    )


def _text(candidate: Any, field: str, default: str = "") -> str:
    return str(getattr(candidate, field, default) or default).strip()


def _risk_blocked(candidate: Any) -> bool:
    hard_risk = getattr(candidate, "hard_risk", None)
    if hard_risk is None:
        return False
    return bool(getattr(hard_risk, "execution_blocked", False) or getattr(hard_risk, "level", "") == "block")


def _input_reasons(candidate: Any) -> list[str]:
    reasons: list[str] = []
    for field in ("exclusion_reasons", "warning_tags"):
        values = getattr(candidate, field, None) or []
        if isinstance(values, (list, tuple, set)):
            reasons.extend(str(item) for item in values if str(item or "").strip())
    return reasons
