from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


EXIT_MODEL_VERSION = "exit-model-v1"
EXIT_MODEL_FEATURE_VERSION = "exit-model-features-v1"
EXIT_MODEL_OBSERVATION_KEY = "paper_exit_model_v1"

ExitModelAction = Literal["hold", "sell_30", "sell_50", "sell_70", "sell_all"]


@dataclass(frozen=True)
class ExitModelFeatureSnapshot:
    symbol: str
    name: str = ""
    strategy_key: str = ""
    as_of: str = ""
    feature_version: str = EXIT_MODEL_FEATURE_VERSION
    current_price: float = 0.0
    cost_basis: float = 0.0
    pnl_pct: float = 0.0
    max_profit_pct: float = 0.0
    pullback_from_high_pct: float = 0.0
    hold_days: int = 0
    quantity: int = 0
    available_quantity: int = 0
    position_pct: float = 0.0
    rule_action: str = "hold"
    rule_sell_ratio: float = 0.0
    quote_quality: str = "unavailable"
    data_quality: str = "unavailable"
    intraday_usable: bool = False
    above_vwap: bool = False
    vwap: float = 0.0
    vwap_deviation_pct: float = 0.0
    rsi: float = 50.0
    atr_pct: float = 0.0
    high_pullback_ratio: float = 0.0
    volume_release_ratio: float = 0.0
    trailing_stop_pct: float = 0.0
    market_state: str = ""
    market_strength: float = 0.0
    sector_strength: float = 0.0
    risk_flags: list[str] = field(default_factory=list)
    feature_values: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExitModelSuggestion:
    action: ExitModelAction = "hold"
    confidence: float = 0.0
    pullback_risk: float = 0.0
    expected_return_next: float = 0.0
    suggested_trailing_stop_pct: float = 0.0
    reasons: list[str] = field(default_factory=list)
    model_version: str = EXIT_MODEL_VERSION
    feature_snapshot: dict[str, Any] = field(default_factory=dict)
    fallback_reason: str | None = None
    shadow_only: bool = True
    data_quality: str = "unavailable"
    rule_action: str = "hold"
    rule_sell_ratio: float = 0.0
    effective_action: str = "hold"
    safety_blocked: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExitModelShadowRecord:
    account_id: int
    position_id: int
    symbol: str
    name: str
    strategy_key: str
    as_of: str
    rule_action: str
    rule_reason: str
    rule_sell_ratio: float
    model_action: str
    model_confidence: float
    model_reason: list[str]
    model_version: str
    fallback_reason: str | None
    feature_snapshot: dict[str, Any]
    outcome_1d: dict[str, Any] = field(default_factory=dict)
    outcome_3d: dict[str, Any] = field(default_factory=dict)
    outcome_5d: dict[str, Any] = field(default_factory=dict)
    outcome_10d: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
