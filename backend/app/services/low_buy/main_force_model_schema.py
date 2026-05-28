from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


MAIN_FORCE_MODEL_VERSION = "main-force-accumulation-washout-markup-v1"
MAIN_FORCE_MODEL_OBSERVATION_KEY = "main_force_accumulation_washout_markup_v1"
MAIN_FORCE_FEATURE_VERSION = "main-force-features-v1"

MainForceStage = Literal["accumulation", "washout", "markup_confirm", "distribution_risk", "unavailable"]
MainForceAction = Literal["observe", "wait_confirm", "buy_probe", "buy_confirmed", "blocked"]
MainForceProductionEffect = Literal["none", "readonly_shadow", "ranking_bonus", "paper_readonly_shadow", "paper_small_position_suggestion"]

STAGE_TEXT: dict[str, str] = {
    "accumulation": "建仓观察",
    "washout": "洗盘确认",
    "markup_confirm": "拉升确认",
    "distribution_risk": "出货风险",
    "unavailable": "不可用",
}

ACTION_TEXT: dict[str, str] = {
    "observe": "观察",
    "wait_confirm": "等确认",
    "buy_probe": "小仓试买",
    "buy_confirmed": "确认买点",
    "blocked": "阻断",
}


@dataclass(frozen=True)
class MainForceFeatureSnapshot:
    symbol: str
    name: str = ""
    strategy_key: str = ""
    as_of_date: str = ""
    max_source_date: str = ""
    feature_version: str = MAIN_FORCE_FEATURE_VERSION
    data_quality: str = "fresh"
    close_price: float = 0.0
    ma5: float = 0.0
    ma10: float = 0.0
    ma20: float = 0.0
    ma60: float = 0.0
    position_60d: float = 0.0
    range_20d_pct: float = 0.0
    volatility_20d: float = 0.0
    drawdown_10d_pct: float = 0.0
    amount_ratio_1d_20d: float = 0.0
    amount_ratio_5d_20d: float = 0.0
    amount_ratio_20d_60d: float = 0.0
    close_position_ratio: float = 0.0
    lower_shadow_ratio: float = 0.0
    upper_shadow_ratio: float = 0.0
    reclaim_ma10: bool = False
    reclaim_ma20: bool = False
    platform_reclaim_20d: bool = False
    trend_above_ma60: bool = False
    market_state: str = ""
    sector_strength: float = 0.0
    market_strength: float = 0.0
    risk_flags: list[str] = field(default_factory=list)
    feature_values: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MainForceAdvice:
    model: str = MAIN_FORCE_MODEL_VERSION
    stage: MainForceStage = "unavailable"
    stage_text: str = "不可用"
    action: MainForceAction = "observe"
    action_text: str = "观察"
    score: float = 0.0
    confidence: float = 0.0
    buy_zone: tuple[float, float] = (0.0, 0.0)
    stop_loss: float = 0.0
    take_profit_plan: list[dict[str, float | str]] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    feature_snapshot: dict[str, Any] = field(default_factory=dict)
    shadow_only: bool = True
    production_effect: MainForceProductionEffect = "none"
    rank_bonus: float = 0.0
    fallback_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["buy_zone"] = list(self.buy_zone)
        return payload


@dataclass(frozen=True)
class MainForceLabelSnapshot:
    as_of_date: str
    label_start_date: str = ""
    label_end_date: str = ""
    max_future_return_20d_pct: float = 0.0
    max_future_return_40d_pct: float = 0.0
    max_adverse_20d_pct: float = 0.0
    future_20d_up_30: bool = False
    future_40d_up_50: bool = False
    hit_stop_loss_20d: bool = False
    positive_quality_label: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
