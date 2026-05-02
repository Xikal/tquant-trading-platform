from __future__ import annotations

from dataclasses import dataclass
from math import log10

import pandas as pd

from app.services.low_buy.shared import BoardCandidate


MAINLINE_TIER_LABELS = {
    "core_mainline": "核心主线",
    "secondary_mainline": "次级主线",
    "rotation_hot": "轮动热点",
    "non_mainline": "非主线",
    "unknown": "主线未知",
}


@dataclass(frozen=True)
class MainlineIndustryScore:
    industry: str
    score: float
    tier: str
    live_rank: int | None = None
    live_change_pct: float = 0.0
    persistence_score: float = 0.0
    pool_score: float = 0.0
    live_score: float = 0.0


@dataclass(frozen=True)
class CandidateMainlineInfo:
    rank: int = 0
    tier: str = "unknown"
    tier_text: str = MAINLINE_TIER_LABELS["unknown"]


def normalize_live_industry_frame(frame: pd.DataFrame | None) -> pd.DataFrame | None:
    if frame is None or frame.empty:
        return None
    normalized = frame.rename(columns={"板块名称": "industry", "涨跌幅": "change_pct"}).copy()
    if "industry" not in normalized.columns or "change_pct" not in normalized.columns:
        return None
    normalized["industry"] = normalized["industry"].astype(str).str.strip()
    normalized["change_pct"] = pd.to_numeric(normalized["change_pct"], errors="coerce")
    normalized = normalized.dropna(subset=["industry", "change_pct"])
    normalized = normalized[normalized["industry"] != ""]
    if normalized.empty:
        return None
    return normalized.sort_values("change_pct", ascending=False).reset_index(drop=True)


def rank_mainline_industries(
    *,
    live_frame: pd.DataFrame | None,
    pooled_candidates: dict[str, BoardCandidate],
    latest_trade_date: str,
    recent_sequences: list[list[str]],
    max_items: int = 5,
) -> list[MainlineIndustryScore]:
    live_scores = _live_industry_scores(live_frame)
    pool_scores = _pool_industry_scores(pooled_candidates, latest_trade_date)
    persistence_scores = _persistence_scores(recent_sequences)
    industries = set(live_scores) | set(pool_scores) | set(persistence_scores)
    if not industries:
        return []

    raw_scores: list[MainlineIndustryScore] = []
    for industry in industries:
        live_score, live_rank, live_change_pct = live_scores.get(industry, (0.0, None, 0.0))
        pool_score = pool_scores.get(industry, 0.0)
        persistence_score = persistence_scores.get(industry, 0.0)
        score = live_score * 0.28 + pool_score * 0.34 + persistence_score * 0.38
        if live_change_pct < -0.2:
            score -= min(12.0, abs(live_change_pct) * 2.0)
        raw_scores.append(
            MainlineIndustryScore(
                industry=industry,
                score=round(max(score, 0.0), 2),
                tier="unknown",
                live_rank=live_rank,
                live_change_pct=round(live_change_pct, 3),
                persistence_score=round(persistence_score, 2),
                pool_score=round(pool_score, 2),
                live_score=round(live_score, 2),
            )
        )

    ordered = sorted(raw_scores, key=lambda item: item.score, reverse=True)
    if not ordered:
        return []
    top_score = max(ordered[0].score, 1.0)
    return [
        MainlineIndustryScore(
            industry=item.industry,
            score=item.score,
            tier=_resolve_mainline_tier(item.score, top_score, index),
            live_rank=item.live_rank,
            live_change_pct=item.live_change_pct,
            persistence_score=item.persistence_score,
            pool_score=item.pool_score,
            live_score=item.live_score,
        )
        for index, item in enumerate(ordered[:max(max_items, 1)])
    ]


def candidate_mainline_info(
    *,
    sector_name: str | None,
    mainline_industries: list[str],
    leader_rank: str,
) -> CandidateMainlineInfo:
    sector = (sector_name or "").strip()
    if not sector or not mainline_industries:
        return CandidateMainlineInfo()
    try:
        rank = mainline_industries.index(sector) + 1
    except ValueError:
        return CandidateMainlineInfo(tier="non_mainline", tier_text=MAINLINE_TIER_LABELS["non_mainline"])
    if rank == 1 and leader_rank in {"leader", "strong_follow"}:
        tier = "core_mainline"
    elif rank <= 2 and leader_rank != "laggard":
        tier = "secondary_mainline"
    elif rank <= 5:
        tier = "rotation_hot"
    else:
        tier = "non_mainline"
    return CandidateMainlineInfo(rank=rank, tier=tier, tier_text=MAINLINE_TIER_LABELS[tier])


def mainline_tier_label(tier: str) -> str:
    return MAINLINE_TIER_LABELS.get(tier, MAINLINE_TIER_LABELS["unknown"])


def _live_industry_scores(frame: pd.DataFrame | None) -> dict[str, tuple[float, int | None, float]]:
    normalized = normalize_live_industry_frame(frame)
    if normalized is None:
        return {}
    scores: dict[str, tuple[float, int | None, float]] = {}
    total = max(len(normalized.index), 1)
    for index, row in normalized.head(30).iterrows():
        industry = str(row["industry"]).strip()
        change_pct = float(row["change_pct"] or 0.0)
        rank_strength = max(0.0, 1.0 - index / max(total, 30))
        change_strength = max(0.0, min((change_pct + 0.3) / 4.8, 1.0))
        score = 100.0 * (rank_strength * 0.55 + change_strength * 0.45)
        scores[industry] = (round(score, 2), int(index) + 1, change_pct)
    return scores


def _pool_industry_scores(
    pooled_candidates: dict[str, BoardCandidate],
    latest_trade_date: str,
) -> dict[str, float]:
    recent_dates = sorted(
        {
            item.board_date
            for item in pooled_candidates.values()
            if item.board_date and item.board_date <= latest_trade_date
        },
        reverse=True,
    )[:5]
    if not recent_dates:
        return {}
    date_weights = {
        trade_date: weight
        for trade_date, weight in zip(recent_dates, (1.0, 0.82, 0.64, 0.45, 0.28))
    }
    raw_scores: dict[str, float] = {}
    for item in pooled_candidates.values():
        industry = item.industry.strip()
        weight = date_weights.get(item.board_date)
        if not industry or weight is None:
            continue
        amount_score = min(3.0, log10(max(item.amount, 1.0)) / 8.5)
        board_score = 1.0 if item.board_count == 1 else 0.58
        raw_scores[industry] = raw_scores.get(industry, 0.0) + weight * (amount_score + board_score)
    return _normalize_score_map(raw_scores)


def _persistence_scores(recent_sequences: list[list[str]]) -> dict[str, float]:
    raw_scores: dict[str, float] = {}
    sequence_weights = (1.0, 0.86, 0.72, 0.55, 0.38)
    rank_weights = (1.0, 0.72, 0.52, 0.35, 0.22)
    for sequence_index, industries in enumerate(recent_sequences[: len(sequence_weights)]):
        sequence_weight = sequence_weights[sequence_index]
        for rank_index, industry in enumerate(_clean_sequence(industries)[: len(rank_weights)]):
            raw_scores[industry] = raw_scores.get(industry, 0.0) + sequence_weight * rank_weights[rank_index]
    return _normalize_score_map(raw_scores)


def _clean_sequence(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        industry = str(value).strip()
        if industry and industry not in result:
            result.append(industry)
    return result


def _normalize_score_map(raw_scores: dict[str, float]) -> dict[str, float]:
    if not raw_scores:
        return {}
    max_score = max(raw_scores.values()) or 1.0
    return {industry: round(score / max_score * 100.0, 2) for industry, score in raw_scores.items()}


def _resolve_mainline_tier(score: float, top_score: float, index: int) -> str:
    if index == 0 and score >= max(38.0, top_score * 0.70):
        return "core_mainline"
    if score >= max(30.0, top_score * 0.55):
        return "secondary_mainline"
    if score >= max(18.0, top_score * 0.35):
        return "rotation_hot"
    return "non_mainline"
