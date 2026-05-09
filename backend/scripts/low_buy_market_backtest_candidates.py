from __future__ import annotations

import pandas as pd

from app.models.schemas import LowBuyCandidateOut
from app.services.low_buy.candidate_metrics import passes_common_prefilter
from app.services.low_buy.candidate_rules import build_strategy_setup, passes_strategy_prefilter, score_candidate
from app.services.low_buy.data_quality import build_low_buy_metrics_quality
from app.services.low_buy.signal_family import build_signal_family_profile, profile_with_setup
from app.services.low_buy.shared import BoardCandidate


def evaluate_candidate_from_metrics(
    *,
    service,
    item: BoardCandidate,
    latest_trade_date: str,
    strategy: str,
    hot_industries: list[str],
    market_regime,
    metrics,
) -> LowBuyCandidateOut | None:
    if not service._passes_candidate_filters(item):
        return None
    if not passes_common_prefilter(item=item, metrics=metrics, strategy=strategy):
        return None
    if not passes_strategy_prefilter(strategy=strategy, item=item, metrics=metrics):
        return None

    metrics_quality = build_low_buy_metrics_quality(metrics)
    if metrics_quality.quality == "unavailable":
        return None
    base_score = score_candidate(
        strategy=strategy,
        item=item,
        metrics=metrics,
        hot_industries=hot_industries,
    )
    signal_profile = build_signal_family_profile(
        strategy=strategy,
        item=item,
        metrics=metrics,
        hot_industries=hot_industries,
    )
    factor_scores = service._factor_scores(metrics, None)
    context_adjustment = service._build_context_adjustment(
        strategy=strategy,
        item=item,
        metrics=metrics,
        hot_industries=hot_industries,
        market_regime=market_regime,
        signal_profile=signal_profile,
        factor_scores=factor_scores,
        metrics_quality=metrics_quality,
    )
    factor_bonus = service._weighted_factor_bonus(factor_scores)
    adjusted_score = max(
        0.0,
        round(base_score + signal_profile.score_bonus + factor_bonus - context_adjustment.score_penalty, 1),
    )
    if adjusted_score < 74 + context_adjustment.score_floor_shift:
        return None

    setup = build_strategy_setup(strategy=strategy, item=item, metrics=metrics, score=adjusted_score)
    signal_profile = profile_with_setup(signal_profile, setup, strategy=strategy)
    return service._build_candidate_output(
        strategy=strategy,
        item=item,
        metrics=metrics,
        score=adjusted_score,
        setup=setup,
        hot_industries=hot_industries,
        context_adjustment=context_adjustment,
        signal_profile=signal_profile,
        factor_scores=factor_scores,
        metrics_quality=metrics_quality,
    )


def dedupe_candidates_for_backtest(candidates: list[LowBuyCandidateOut]) -> list[LowBuyCandidateOut]:
    deduped: dict[tuple[str, str], LowBuyCandidateOut] = {}
    for candidate in candidates:
        deduped[(candidate.strategy_key, candidate.symbol)] = candidate
    return list(deduped.values())


def iter_snapshot_candidates(payload) -> list[LowBuyCandidateOut]:
    candidates = list(payload.confirmed_candidates) + list(payload.candidates)
    return dedupe_candidates_for_backtest(candidates)


def refresh_candidate_signal(service, candidate: LowBuyCandidateOut, history: pd.DataFrame) -> LowBuyCandidateOut | None:
    latest_rows = history.index[history["date"] == candidate.confirmed_trade_date].tolist()
    if not latest_rows:
        return None
    return service._refresh_historical_buy_signal(candidate, history.iloc[latest_rows[-1]])
