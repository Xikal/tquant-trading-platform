from __future__ import annotations

from typing import Any

from app.models.entities import LowBuyResultSnapshot
from app.repositories.low_buy import LowBuyResultRepository
from app.services.low_buy.recommendation_duration import attach_response_recommendation_durations
from app.services.low_buy.result_snapshots import build_materialized_response
from app.services.low_buy.shared import LowBuyCandidateOut, LowBuyScreenerResponse, Session


def load_materialized_full_result(
    owner: Any,
    *,
    db: Session,
    strategy: str,
    latest_trade_date: str,
    limit: int,
    include_history: bool,
) -> LowBuyScreenerResponse | None:
    summary = LowBuyResultRepository(db).fetch_scan_summary(
        latest_trade_date=latest_trade_date,
        strategy_key=strategy,
    )
    if summary is None or not owner._materialized_scan_is_current(
        db=db,
        strategy=strategy,
        latest_trade_date=latest_trade_date,
        summary=summary,
    ):
        return None
    summary_filters = owner._safe_json_object(summary.filters_json)
    rows = LowBuyResultRepository(db).fetch_results(
        latest_trade_date=latest_trade_date,
        strategy_key=strategy,
    )
    candidates = owner._deserialize_candidates(rows) if rows else []
    dedupe_candidates = getattr(owner, "_dedupe_candidates", _dedupe_candidates_by_symbol)
    signal_rank = getattr(owner, "_signal_rank", _default_signal_rank)
    candidates = dedupe_candidates(candidates)
    candidates.sort(key=lambda item: (signal_rank(item.buy_signal_state), item.score), reverse=True)
    confirmed_candidates = [
        item for item in candidates if item.buy_signal_state in owner._confirmed_signal_states
    ][:12]
    watch_candidates = [
        item for item in candidates if item.buy_signal_state not in owner._confirmed_signal_states
    ][:limit]
    history_sections = []
    if include_history and strategy == "classic_retrace":
        completed_trade_dates = [item for item in owner._get_recent_trade_dates(14) if item <= latest_trade_date]
        history_sections = owner._build_history_sections(
            completed_trade_dates[-4:-1],
            strategy,
            db=db,
        )

    payload = build_materialized_response(
        summary=summary,
        summary_filters=summary_filters,
        confirmed_candidates=confirmed_candidates,
        watch_candidates=watch_candidates,
        history_sections=history_sections,
    )
    return attach_response_recommendation_durations(db=db, payload=payload)


def deserialize_candidates(owner: Any, rows: list[LowBuyResultSnapshot]) -> list[LowBuyCandidateOut]:
    candidates: list[LowBuyCandidateOut] = []
    for row in rows:
        if not owner._candidate_payload_is_current(row.payload_json):
            continue
        try:
            candidate = LowBuyCandidateOut.model_validate_json(row.payload_json)
        except Exception:
            continue
        candidates.append(owner._normalize_candidate_policy_state(candidate))
    return candidates


def load_materialized_candidates_by_symbol(
    owner: Any,
    *,
    db: Session,
    strategy: str,
    latest_trade_date: str,
    symbols: list[str],
) -> dict[str, LowBuyCandidateOut]:
    if not symbols:
        return {}
    if not owner._materialized_scan_is_current(
        db=db,
        strategy=strategy,
        latest_trade_date=latest_trade_date,
    ):
        return {}
    rows = LowBuyResultRepository(db).fetch_results_for_symbols(
        latest_trade_date=latest_trade_date,
        strategy_key=strategy,
        symbols=symbols,
    )
    performance = owner._load_strategy_performance_snapshot(
        db=db,
        strategy=strategy,
        latest_trade_date=latest_trade_date,
    )
    result: dict[str, LowBuyCandidateOut] = {}
    for row in rows:
        if not owner._candidate_payload_is_current(row.payload_json):
            continue
        try:
            candidate = LowBuyCandidateOut.model_validate_json(row.payload_json)
        except Exception:
            continue
        candidate = owner._normalize_candidate_policy_state(candidate)
        result[row.symbol] = owner._apply_candidate_positioning(candidate, performance)
    return result


def _default_signal_rank(state: str) -> int:
    return {"buy_now": 4, "soft_buy_now": 3, "near_entry": 2, "watch": 1}.get(state, 0)


def _dedupe_candidates_by_symbol(items: list[LowBuyCandidateOut]) -> list[LowBuyCandidateOut]:
    seen: set[str] = set()
    result: list[LowBuyCandidateOut] = []
    for item in items:
        if item.symbol in seen:
            continue
        seen.add(item.symbol)
        result.append(item)
    return result
