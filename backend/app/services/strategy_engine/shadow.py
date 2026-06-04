from __future__ import annotations

from typing import Any

from app.services.strategy_engine.low_buy_adapter import low_buy_strategy_engine_output


def low_buy_strategy_engine_shadow_payload(
    candidate: Any,
    *,
    current_production_score: float | None,
    current_watch_score: float | None,
    market_context: Any | None = None,
    strategy_variant: str = "baseline",
) -> dict[str, Any]:
    output = low_buy_strategy_engine_output(
        candidate,
        market_context=market_context,
        strategy_variant=strategy_variant,
    )
    payload = output.as_payload()
    parity_status = _parity_status(
        current_production_score=current_production_score,
        current_watch_score=current_watch_score,
        strategy_engine_production_score=output.production_score,
        strategy_engine_watch_score=output.watch_score,
    )
    return {
        "strategy_engine_shadow": {
            **payload,
            "shadow_only": True,
            "replacement_enabled": False,
            "production_sort_replaced": False,
            "parity_status": parity_status,
            "production_score_delta": _score_delta(output.production_score, current_production_score),
            "watch_score_delta": _score_delta(output.watch_score, current_watch_score),
        },
        "strategy_engine_decision": output.decision,
        "strategy_engine_warning_tags": list(output.warning_tags),
        "strategy_engine_exclusion_reasons": list(output.exclusion_reasons),
        "strategy_engine_score_delta": _score_delta(output.production_score, current_production_score),
        "strategy_engine_parity_status": parity_status,
    }


def _parity_status(
    *,
    current_production_score: float | None,
    current_watch_score: float | None,
    strategy_engine_production_score: float | None,
    strategy_engine_watch_score: float | None,
) -> str:
    production_matches = _scores_match(current_production_score, strategy_engine_production_score)
    watch_matches = _scores_match(current_watch_score, strategy_engine_watch_score)
    if production_matches and watch_matches:
        return "match"
    if not production_matches:
        return "production_score_delta"
    return "watch_score_delta"


def _score_delta(left: float | None, right: float | None) -> float | None:
    if left is None and right is None:
        return 0.0
    if left is None or right is None:
        return None
    return round(float(left) - float(right), 4)


def _scores_match(left: float | None, right: float | None) -> bool:
    delta = _score_delta(left, right)
    return delta == 0.0
