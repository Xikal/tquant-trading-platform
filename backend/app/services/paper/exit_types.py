from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


PaperExitActionSignal = Literal[
    "hold",
    "washout",
    "hard_stop",
    "time_stop",
    "profit_take",
    "scale_out",
]


@dataclass(frozen=True)
class PaperExitDecision:
    quantity: int
    reason: str
    code: str
    pnl_pct: float
    hold_days: int
    sell_ratio: float
    strategy_key: str
    action_signal: PaperExitActionSignal = "hold"
    action_text: str = "继续观察"
    why: str = ""
    invalid_condition: str = ""
    failure_action: str = ""
    fee_drag_pct: float = 0.0
    net_profit_pct: float = 0.0
