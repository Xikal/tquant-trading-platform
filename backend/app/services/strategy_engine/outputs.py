from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


ProductionDecision = Literal[
    "production_candidate",
    "watch_only",
    "research_only",
    "shadow_paper_only",
    "blocked",
]


@dataclass(frozen=True)
class StrategyEngineOutput:
    """Canonical strategy output envelope.

    This is an architecture boundary object. It does not replace existing
    low-buy scoring or priority-board ordering; adapters can map existing
    results into this shape while domain modules are gradually decoupled.
    """

    strategy_key: str
    symbol: str = ""
    signal_state: str = "watch"
    production_score: float | None = None
    watch_score: float | None = None
    score_components: dict[str, float] = field(default_factory=dict)
    exclusion_reasons: list[str] = field(default_factory=list)
    warning_tags: list[str] = field(default_factory=list)
    decision: ProductionDecision = "watch_only"
    engine_version: str = "strategy-engine-boundary-v1"
    source: str = "adapter"
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_payload(self) -> dict[str, Any]:
        return {
            "strategy_key": self.strategy_key,
            "symbol": self.symbol,
            "signal_state": self.signal_state,
            "production_score": self.production_score,
            "watch_score": self.watch_score,
            "score_components": dict(self.score_components),
            "exclusion_reasons": list(self.exclusion_reasons),
            "warning_tags": list(self.warning_tags),
            "decision": self.decision,
            "engine_version": self.engine_version,
            "source": self.source,
            "metadata": dict(self.metadata),
        }
