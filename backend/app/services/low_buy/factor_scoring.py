from __future__ import annotations

from app.services.low_buy.candidate_types import CandidateMetrics
from app.services.low_buy.factor_external import (
    evaluate_big_order_flow_factor,
    evaluate_event_risk_factor,
)
from app.services.low_buy.factor_functions import (
    evaluate_registered_external_factors,
    get_effective_factor_weights,
)
from app.services.low_buy.factor_types import FactorContext
from app.services.low_buy.selection_quality_factor import evaluate_selection_quality_factor
from app.services.low_buy.shared import LOW_BUY_THRESHOLDS
from app.services.low_buy.signal_family import (
    evaluate_absorption_quality_factor,
    evaluate_deep_pullback_factor,
    evaluate_gap_risk_factor,
    evaluate_price_structure_factor,
    evaluate_sector_density_factor,
    evaluate_sector_flow_factor,
    evaluate_shrink_quality_factor,
    evaluate_signal_freshness_factor,
    evaluate_time_efficiency_factor,
    evaluate_trend_rebound_factor,
    evaluate_volatility_regime_factor,
)


def build_factor_scores(metrics: CandidateMetrics, context: FactorContext | None = None) -> dict[str, float]:
    scores = {
        "deep_pullback_factor": evaluate_deep_pullback_factor(metrics),
        "trend_rebound_factor": evaluate_trend_rebound_factor(metrics),
        "shrink_quality_factor": evaluate_shrink_quality_factor(metrics),
        "gap_risk_factor": evaluate_gap_risk_factor(metrics),
        "volatility_regime_factor": evaluate_volatility_regime_factor(metrics),
        "time_efficiency_factor": evaluate_time_efficiency_factor(metrics),
        "price_structure_factor": evaluate_price_structure_factor(metrics),
        "sector_density_factor": evaluate_sector_density_factor(context),
        "sector_flow_factor": evaluate_sector_flow_factor(context),
        "signal_freshness_factor": evaluate_signal_freshness_factor(context),
        "absorption_quality_factor": evaluate_absorption_quality_factor(),
        "selection_quality_factor": evaluate_selection_quality_factor(metrics),
    }
    if context is not None and context.current_symbol:
        scores["big_order_flow_factor"] = evaluate_big_order_flow_factor(
            symbol=context.current_symbol,
            retracement_days=context.retracement_days,
        )
        scores["event_risk_factor"] = evaluate_event_risk_factor(symbol=context.current_symbol)
    scores.update(evaluate_registered_external_factors(metrics, context))
    return _visible_scores(scores, context)


def weighted_factor_bonus(factor_scores: dict[str, float]) -> float:
    factor_weights = get_effective_factor_weights()
    weighted = sum(
        max(float(value), 0.0) * factor_weights.get(key, 1.0)
        for key, value in factor_scores.items()
    )
    return min(LOW_BUY_THRESHOLDS.MAX_FACTOR_BONUS, weighted)


def _visible_scores(scores: dict[str, float], context: FactorContext | None) -> dict[str, float]:
    filtered = {key: value for key, value in scores.items() if value > 0}
    if context is not None and context.current_symbol:
        filtered.setdefault("big_order_flow_factor", scores.get("big_order_flow_factor", 0.0))
        filtered.setdefault("event_risk_factor", scores.get("event_risk_factor", 0.0))
    return filtered
