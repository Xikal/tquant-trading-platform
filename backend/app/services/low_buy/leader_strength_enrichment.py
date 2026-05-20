from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.schemas import LowBuyCandidateOut
from app.services.low_buy.priority_types import PriorityCandidate
from app.services.market_data import MarketDataService


def enrich_priority_candidates_with_leader_strength(
    *,
    db: Session,
    rows: list[PriorityCandidate],
    market_data: MarketDataService | None = None,
) -> list[PriorityCandidate]:
    if not rows:
        return rows
    try:
        response = (market_data or MarketDataService()).sector_relative_strength_rank(db, limit=8, per_sector_limit=30)
    except Exception:
        return rows
    score_by_symbol = {item.symbol: float(item.leader_score or 0.0) for item in response.items}
    rank_by_symbol = {item.symbol: int(item.rank or 0) for item in response.items}
    text_by_symbol = {
        item.symbol: f"{item.sector_name}板块内第{item.rank}，龙头分{item.leader_score:.1f}"
        for item in response.items
    }
    for row in rows:
        leader_score = score_by_symbol.get(row.symbol)
        if leader_score is None:
            continue
        bonus = _leader_bonus(leader_score, rank_by_symbol.get(row.symbol, 0))
        for hit in row.hits:
            candidate = hit.candidate
            hit.candidate = candidate.model_copy(
                update={
                    "score": round(min(99.0, float(candidate.score or 0.0) + bonus), 1),
                    "leader_strength_score": round(leader_score, 2),
                    "leader_strength_rank": rank_by_symbol.get(row.symbol, 0),
                    "leader_strength_text": text_by_symbol.get(row.symbol, ""),
                }
            )
    return rows


def enrich_low_buy_candidates_with_leader_strength(
    *,
    db: Session,
    candidates: list[LowBuyCandidateOut],
    market_data: MarketDataService | None = None,
) -> list[LowBuyCandidateOut]:
    if not candidates:
        return candidates
    try:
        response = (market_data or MarketDataService()).sector_relative_strength_rank(db, limit=8, per_sector_limit=30)
    except Exception:
        return candidates
    score_by_symbol = {item.symbol: float(item.leader_score or 0.0) for item in response.items}
    rank_by_symbol = {item.symbol: int(item.rank or 0) for item in response.items}
    text_by_symbol = {
        item.symbol: f"{item.sector_name}板块内第{item.rank}，龙头分{item.leader_score:.1f}"
        for item in response.items
    }
    enriched: list[LowBuyCandidateOut] = []
    for candidate in candidates:
        leader_score = score_by_symbol.get(candidate.symbol)
        if leader_score is None:
            enriched.append(candidate)
            continue
        bonus = _leader_bonus(leader_score, rank_by_symbol.get(candidate.symbol, 0))
        enriched.append(
            candidate.model_copy(
                update={
                    "score": round(min(99.0, float(candidate.score or 0.0) + bonus), 1),
                    "leader_strength_score": round(leader_score, 2),
                    "leader_strength_rank": rank_by_symbol.get(candidate.symbol, 0),
                    "leader_strength_text": text_by_symbol.get(candidate.symbol, ""),
                }
            )
        )
    return enriched


def _leader_bonus(score: float, rank: int) -> float:
    base = max(0.0, (score - 55.0) / 9.0)
    rank_bonus = {1: 2.0, 2: 1.2, 3: 0.6}.get(rank, 0.0)
    return round(min(6.0, base + rank_bonus), 2)
