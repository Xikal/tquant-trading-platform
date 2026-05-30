from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FactorContext:
    """因子评估所需的跨候选上下文。"""

    sector_pass_counts: dict[str, int] = field(default_factory=dict)
    sector_flow_ranks: dict[str, float] = field(default_factory=dict)
    current_sector: str = ""
    current_symbol: str = ""
    retracement_days: int = 0
    confirmed_trade_date: str = ""
    current_date: str = ""
    total_strategies: int = 0
    allow_realtime_external_factors: bool = False
