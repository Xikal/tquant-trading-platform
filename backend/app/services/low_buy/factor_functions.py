from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.entities import SystemSetting
from app.services.low_buy.candidate_types import CandidateMetrics
from app.services.low_buy.factor_external import (
    evaluate_block_trade_premium_factor,
    evaluate_dragon_board_factor,
    evaluate_earnings_surprise_factor,
    evaluate_insider_trade_factor,
    evaluate_limit_up_quality_factor,
    evaluate_margin_balance_factor,
    evaluate_north_flow_factor,
    evaluate_pre_market_auction_factor,
    evaluate_short_balance_factor,
)
from app.services.low_buy.factor_types import FactorContext
from app.services.low_buy.shared import LOW_BUY_THRESHOLDS


FactorEvaluator = Callable[[CandidateMetrics, Optional[FactorContext]], float]


@dataclass(frozen=True)
class FactorSpec:
    name: str
    weight: float
    data_dependencies: tuple[str, ...] = field(default_factory=tuple)
    applicable_strategies: tuple[str, ...] = field(default_factory=tuple)
    activation_condition: str = "always"
    status: str = "active"
    status_text: str = "已启用"
    evaluator: FactorEvaluator | None = None


_WEIGHT_CACHE: tuple[float, dict[str, float]] | None = None
_WEIGHT_CACHE_TTL_SECONDS = 15.0
_WEIGHT_CACHE_LOCK = threading.Lock()
FACTOR_WEIGHT_SETTING_KEY = "factor_weights"


def list_factor_specs() -> list[FactorSpec]:
    """Return the single registry of factor definitions.

    External-data factors default to 0 until their data source is configured.
    This keeps the strategy chain stable while making future factor additions
    a registry-only change.
    """

    defaults = LOW_BUY_THRESHOLDS.FACTOR_WEIGHTS
    return [
        FactorSpec("deep_pullback_factor", defaults.get("deep_pullback_factor", 1.0), ("daily_bars",)),
        FactorSpec("trend_rebound_factor", defaults.get("trend_rebound_factor", 0.8), ("daily_bars",), status="experimental", status_text="研究中"),
        FactorSpec("sector_density_factor", defaults.get("sector_density_factor", 1.2), ("hot_industries",)),
        FactorSpec("shrink_quality_factor", defaults.get("shrink_quality_factor", 1.0), ("daily_bars",)),
        FactorSpec("gap_risk_factor", defaults.get("gap_risk_factor", 1.5), ("daily_bars",)),
        FactorSpec("volatility_regime_factor", defaults.get("volatility_regime_factor", 0.7), ("daily_bars",)),
        FactorSpec("time_efficiency_factor", defaults.get("time_efficiency_factor", 0.6), ("signal_date",)),
        FactorSpec("signal_freshness_factor", defaults.get("signal_freshness_factor", 0.5), ("signal_date",)),
        FactorSpec("sector_flow_factor", defaults.get("sector_flow_factor", 0.7), ("sector_flow",), status="experimental", status_text="研究中"),
        FactorSpec("big_order_flow_factor", defaults.get("big_order_flow_factor", 0.4), ("big_order_flow",), status="experimental", status_text="研究中"),
        FactorSpec("price_structure_factor", defaults.get("price_structure_factor", 0.9), ("daily_bars",)),
        FactorSpec("event_risk_factor", defaults.get("event_risk_factor", 0.6), ("event_risk",), status="experimental", status_text="研究中"),
        FactorSpec("absorption_quality_factor", defaults.get("absorption_quality_factor", 0.5), ("intraday_bars",), status="experimental", status_text="研究中"),
        FactorSpec("north_flow_factor", 1.0, ("north_flow",), ("first_board", "ma_support", "classic_retrace"), status="stub", status_text="未启用，数据源未接入"),
        FactorSpec("dragon_board_factor", 0.8, ("dragon_board",), ("classic_retrace", "volume_shrink", "first_board"), status="stub", status_text="未启用，数据源未接入"),
        FactorSpec("limit_up_quality_factor", 0.9, ("limit_up_board",), ("first_board", "divergence_consensus"), status="stub", status_text="未启用，数据源未接入"),
        FactorSpec("pre_market_auction_factor", 0.6, ("auction_snapshot",), ("late_session_strong_support", "first_board"), status="stub", status_text="未启用，数据源未接入"),
        FactorSpec("margin_balance_factor", 0.5, ("margin_balance",), ("deep_pullback", "trend_rebound"), status="stub", status_text="未启用，数据源未接入"),
        FactorSpec("block_trade_premium_factor", 0.4, ("block_trade",), ("breakout_support", "ma_support"), status="stub", status_text="未启用，数据源未接入"),
        FactorSpec("earnings_surprise_factor", 0.3, ("earnings_calendar",), (), status="stub", status_text="未启用，数据源未接入"),
        FactorSpec("insider_trade_factor", 0.5, ("announcements",), (), status="stub", status_text="未启用，数据源未接入"),
        FactorSpec("short_balance_factor", 0.7, ("short_balance",), (), status="stub", status_text="未启用，数据源未接入"),
    ]


def default_factor_weights() -> dict[str, float]:
    return {spec.name: float(spec.weight) for spec in list_factor_specs()}


def get_effective_factor_weights() -> dict[str, float]:
    defaults = default_factor_weights()
    overrides = _load_factor_weight_overrides()
    for key, value in overrides.items():
        if key in defaults:
            defaults[key] = _clamp_weight(value)
    return defaults


def save_factor_weight_overrides(weights: dict[str, float]) -> dict[str, float]:
    cleaned = {
        key: _clamp_weight(value)
        for key, value in weights.items()
        if key in default_factor_weights()
    }
    with SessionLocal() as db:
        row = db.execute(
            select(SystemSetting).where(SystemSetting.key == FACTOR_WEIGHT_SETTING_KEY)
        ).scalar_one_or_none()
        if row is None:
            row = SystemSetting(key=FACTOR_WEIGHT_SETTING_KEY, value=json.dumps(cleaned, ensure_ascii=False))
            db.add(row)
        else:
            row.value = json.dumps(cleaned, ensure_ascii=False)
        db.commit()
    clear_factor_weight_cache()
    return get_effective_factor_weights()


def clear_factor_weight_cache() -> None:
    global _WEIGHT_CACHE
    with _WEIGHT_CACHE_LOCK:
        _WEIGHT_CACHE = None


def evaluate_registered_external_factors(
    metrics: CandidateMetrics,
    context: Optional[FactorContext],
) -> dict[str, float]:
    """Evaluate newly registered optional factors.

    These factors intentionally return 0 when the required external data is not
    available.  A missing data source should not create false confidence or
    slow down the default screening path.
    """

    symbol = context.current_symbol if context else ""
    return {
        "north_flow_factor": evaluate_north_flow_factor(),
        "dragon_board_factor": evaluate_dragon_board_factor(symbol) if symbol else 0.0,
        "limit_up_quality_factor": evaluate_limit_up_quality_factor(symbol) if symbol else 0.0,
        "pre_market_auction_factor": evaluate_pre_market_auction_factor(symbol) if symbol else 0.0,
        "margin_balance_factor": evaluate_margin_balance_factor(symbol) if symbol else 0.0,
        "block_trade_premium_factor": evaluate_block_trade_premium_factor(symbol) if symbol else 0.0,
        "earnings_surprise_factor": evaluate_earnings_surprise_factor(symbol) if symbol else 0.0,
        "insider_trade_factor": evaluate_insider_trade_factor(symbol) if symbol else 0.0,
        "short_balance_factor": evaluate_short_balance_factor(symbol) if symbol else 0.0,
    }


def _load_factor_weight_overrides() -> dict[str, float]:
    global _WEIGHT_CACHE
    now = time.monotonic()
    if _WEIGHT_CACHE and now - _WEIGHT_CACHE[0] < _WEIGHT_CACHE_TTL_SECONDS:
        return dict(_WEIGHT_CACHE[1])
    with _WEIGHT_CACHE_LOCK:
        now = time.monotonic()
        if _WEIGHT_CACHE and now - _WEIGHT_CACHE[0] < _WEIGHT_CACHE_TTL_SECONDS:
            return dict(_WEIGHT_CACHE[1])
        overrides: dict[str, float] = {}
        try:
            with SessionLocal() as db:
                row = db.execute(
                    select(SystemSetting).where(SystemSetting.key == FACTOR_WEIGHT_SETTING_KEY)
                ).scalar_one_or_none()
                if row and row.value:
                    raw = json.loads(row.value)
                    if isinstance(raw, dict):
                        overrides = {
                            str(key): float(value)
                            for key, value in raw.items()
                            if isinstance(value, (int, float, str))
                        }
        except Exception:
            overrides = {}
        _WEIGHT_CACHE = (now, overrides)
        return dict(overrides)


def _clamp_weight(value: float | int | str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.0
    return round(min(2.0, max(0.0, numeric)), 3)


def _evaluate_unavailable_factor(
    _metrics: CandidateMetrics,
    _context: Optional[FactorContext],
) -> float:
    return 0.0
