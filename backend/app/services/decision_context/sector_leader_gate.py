from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.models.schema_defs.decision_context import GateDecisionOut
from app.models.schema_defs.market import SectorRelativeStrengthResponse
from app.services.low_buy.strategy_policy import StrategyTier, get_strategy_tier, participates_in_priority_board


CORE_SECTOR_LEADER_BOOST_CAP = 12.0
AUX_SECTOR_LEADER_BOOST_CAP = 6.0


@dataclass(frozen=True)
class SectorLeaderGateInput:
    strategy_key: str = "first_board"
    sector_name: str = ""
    sector_rank: int | None = None
    sector_strength_score: float | None = None
    leader_score: float | None = None
    leader_rank: int | None = None
    same_sector_limit_up_count: int | None = None
    diffusion_score: float | None = None
    turnover_confirmation_score: float | None = None
    data_quality: str = "ok"


def evaluate_sector_leader_gate(value: SectorLeaderGateInput) -> GateDecisionOut:
    if not _sector_leader_gate_enabled():
        return GateDecisionOut(decision="allow", score=100.0, reasons=[], evidence={"feature_flag_disabled": True})
    if value.strategy_key and not participates_in_priority_board(value.strategy_key):
        return GateDecisionOut(
            decision="research_only",
            score=0.0,
            reasons=["研究层策略不获得板块/龙头生产先验。"],
            evidence={"strategy_key": value.strategy_key, "data_quality": value.data_quality or "ok"},
        )
    if not str(value.sector_name or "").strip() and value.sector_rank is None and value.sector_strength_score is None:
        return GateDecisionOut(
            decision="research_only",
            score=0.0,
            reasons=["板块归属缺失，该票仅保留研究态。"],
            evidence={"data_quality": "missing"},
        )

    sector_score = _sector_strength(value.sector_rank, value.sector_strength_score)
    leader_score = _leader_health(value.leader_score, value.leader_rank)
    diffusion = _diffusion(value.diffusion_score, value.same_sector_limit_up_count)
    turnover = _bounded(value.turnover_confirmation_score, default=50.0)
    score = round(sector_score * 0.35 + leader_score * 0.30 + diffusion * 0.20 + turnover * 0.15, 2)
    leader_status = _leader_status(leader_score)
    break_reason = _leader_break_reason(leader_status, diffusion, value.same_sector_limit_up_count)
    evidence = {
        "strategy_key": value.strategy_key,
        "sector_name": value.sector_name,
        "sector_rank": value.sector_rank,
        "sector_strength_score": round(sector_score, 2),
        "leader_score": round(float(value.leader_score or 0.0), 2),
        "leader_rank": value.leader_rank or 0,
        "leader_status": leader_status,
        "leader_break_reason": break_reason,
        "same_sector_limit_up_count": int(value.same_sector_limit_up_count or 0),
        "diffusion_score": round(diffusion, 2),
        "turnover_confirmation_score": round(turnover, 2),
        "data_quality": value.data_quality or "ok",
    }
    if leader_status == "broken" and leader_score < 30.0 and diffusion < 20:
        return GateDecisionOut(decision="block", score=score, reasons=["龙头走弱且板块扩散不足，生产候选阻断。"], evidence=evidence)
    if score >= 75.0 and leader_status == "healthy" and diffusion >= 55.0:
        return GateDecisionOut(decision="allow", score=score, reasons=["板块扩散、龙头健康与换手确认支持生产加权。"], evidence=evidence)
    return GateDecisionOut(
        decision="reduce",
        score=max(35.0, min(score, 74.0)),
        reasons=["孤立题材或板块扩散不足，生产加权降级。"],
        evidence=evidence,
    )


def sector_leader_gate_from_candidate(candidate: Any, market_context: Any | None = None) -> GateDecisionOut:
    sector_name = str(getattr(candidate, "sector_name", "") or "")
    industry_ranks = getattr(market_context, "industry_ranks", {}) or {}
    sector_rank = None
    if sector_name in industry_ranks:
        sector_rank = int(industry_ranks[sector_name]) + 1
    leader_score = float(getattr(candidate, "leader_strength_score", 0.0) or 0.0)
    leader_rank = int(getattr(candidate, "leader_strength_rank", 0) or 0) or None
    same_sector_limit_up_count = _candidate_sector_limit_count(candidate, market_context)
    diffusion_score = _candidate_diffusion_score(candidate, market_context, same_sector_limit_up_count)
    turnover_confirmation_score = _bounded(float(getattr(candidate, "volume_burst_ratio", 0.0) or 0.0) * 35.0, default=45.0)
    return evaluate_sector_leader_gate(
        SectorLeaderGateInput(
            strategy_key=str(getattr(candidate, "strategy_key", "") or ""),
            sector_name=sector_name,
            sector_rank=sector_rank,
            sector_strength_score=_candidate_sector_strength(candidate, sector_rank),
            leader_score=leader_score if leader_score > 0 else None,
            leader_rank=leader_rank,
            same_sector_limit_up_count=same_sector_limit_up_count,
            diffusion_score=diffusion_score,
            turnover_confirmation_score=turnover_confirmation_score,
            data_quality=str(getattr(candidate, "data_quality", "ok") or "ok"),
        )
    )


def apply_sector_leader_gate_to_score(
    score: float | None,
    gate: GateDecisionOut,
    strategy_key: str,
) -> tuple[float | None, float]:
    if score is None or not participates_in_priority_board(strategy_key):
        return score, 0.0
    if gate.evidence.get("feature_flag_disabled"):
        return score, 0.0
    if gate.decision in {"block", "research_only", "no_data"}:
        return None, 0.0
    if gate.decision != "allow":
        return score, 0.0
    cap = _boost_cap(strategy_key)
    if cap <= 0:
        return score, 0.0
    boost = round(max(0.0, min(cap, (float(gate.score) - 70.0) / 30.0 * cap)), 1)
    return round(min(100.0, float(score) + boost), 2), boost


def enrich_sector_relative_strength_response(
    response: SectorRelativeStrengthResponse,
    *,
    market_context: Any | None = None,
) -> SectorRelativeStrengthResponse:
    items = list(response.items or [])
    sector_counts = _visible_limit_up_counts(items)
    enriched = []
    hot_industries = list(getattr(market_context, "hot_industries", []) or [])
    for item in items:
        same_sector_limit_up_count = max(
            sector_counts.get(item.sector_name, 0),
            1 if float(item.leader_score or 0.0) >= 75.0 or float(item.change_pct or 0.0) >= 5.0 else 0,
        )
        diffusion_score = _response_diffusion_score(
            sector_name=item.sector_name,
            item_count=sum(1 for other in items if other.sector_name == item.sector_name),
            same_sector_limit_up_count=same_sector_limit_up_count,
            leader_score=float(item.leader_score or 0.0),
            hot_industries=hot_industries,
        )
        gate = evaluate_sector_leader_gate(
            SectorLeaderGateInput(
                strategy_key="first_board",
                sector_name=item.sector_name,
                sector_rank=_sector_rank_from_response(item.sector_name, items),
                sector_strength_score=float(item.leader_score or 0.0),
                leader_score=float(item.leader_score or 0.0),
                leader_rank=int(item.rank or 0),
                same_sector_limit_up_count=same_sector_limit_up_count,
                diffusion_score=diffusion_score,
                turnover_confirmation_score=_bounded(float(item.volume_ratio or 0.0) * 34.0 + float(item.turnover_proxy or 0.0) * 15.0, default=50.0),
            )
        )
        enriched.append(
            item.model_copy(
                update={
                    "leader_status": str(gate.evidence.get("leader_status") or "unknown"),
                    "leader_break_reason": str(gate.evidence.get("leader_break_reason") or ""),
                    "same_sector_limit_up_count": int(gate.evidence.get("same_sector_limit_up_count") or 0),
                    "diffusion_score": float(gate.evidence.get("diffusion_score") or 0.0),
                    "sector_leader_gate_decision": gate.decision,
                }
            )
        )
    return response.model_copy(update={"items": enriched})


def _sector_strength(rank: int | None, explicit_score: float | None) -> float:
    if explicit_score is not None:
        return _bounded(explicit_score, default=50.0)
    if rank is None or rank <= 0:
        return 42.0
    return max(20.0, 100.0 - min(rank - 1, 12) * 7.5)


def _leader_health(leader_score: float | None, leader_rank: int | None) -> float:
    base = _bounded(leader_score, default=45.0)
    if leader_rank and leader_rank > 0:
        base += {1: 10.0, 2: 6.0, 3: 3.0}.get(leader_rank, -min(14.0, (leader_rank - 3) * 1.8))
    return _bounded(base, default=45.0)


def _diffusion(explicit_score: float | None, limit_up_count: int | None) -> float:
    count_score = min(100.0, max(0, int(limit_up_count or 0)) * 18.0)
    if explicit_score is None:
        return count_score
    return max(_bounded(explicit_score, default=0.0), count_score)


def _leader_status(leader_score: float) -> str:
    if leader_score >= 72.0:
        return "healthy"
    if leader_score >= 35.0:
        return "watch"
    return "broken"


def _leader_break_reason(leader_status: str, diffusion_score: float, limit_up_count: int | None) -> str:
    if leader_status == "healthy" and diffusion_score >= 55.0:
        return ""
    if leader_status == "broken":
        return "leader_score_broken"
    if int(limit_up_count or 0) <= 0 or diffusion_score < 35.0:
        return "sector_diffusion_weak"
    return "leader_confirmation_wait"


def _boost_cap(strategy_key: str) -> float:
    tier = get_strategy_tier(strategy_key)
    if tier == StrategyTier.CORE:
        return CORE_SECTOR_LEADER_BOOST_CAP
    if tier == StrategyTier.AUXILIARY:
        return AUX_SECTOR_LEADER_BOOST_CAP
    return 0.0


def _candidate_sector_limit_count(candidate: Any, market_context: Any | None) -> int:
    sector_name = str(getattr(candidate, "sector_name", "") or "")
    hot_industries = list(getattr(market_context, "hot_industries", []) or [])
    if sector_name and sector_name in hot_industries[:3]:
        return max(1, min(6, int(getattr(market_context, "limit_up_count", 0) or 0) // 12))
    return 0


def _candidate_diffusion_score(candidate: Any, market_context: Any | None, limit_up_count: int) -> float:
    sector_name = str(getattr(candidate, "sector_name", "") or "")
    hot_industries = list(getattr(market_context, "hot_industries", []) or [])
    if sector_name and sector_name in hot_industries[:3]:
        rank_bonus = max(0.0, 30.0 - hot_industries.index(sector_name) * 8.0)
    else:
        rank_bonus = 0.0
    tier_bonus = {
        "core_mainline": 26.0,
        "secondary_mainline": 18.0,
        "rotation_hot": 10.0,
    }.get(str(getattr(candidate, "mainline_tier", "") or ""), 0.0)
    return max(0.0, min(100.0, rank_bonus + tier_bonus + limit_up_count * 11.0))


def _candidate_sector_strength(candidate: Any, sector_rank: int | None) -> float:
    tier = str(getattr(candidate, "industry_tier", "") or "")
    if tier in {"core_hot", "secondary_hot"}:
        return 82.0 if tier == "core_hot" else 72.0
    return _sector_strength(sector_rank, None)


def _visible_limit_up_counts(items: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        if float(getattr(item, "change_pct", 0.0) or 0.0) >= 9.5:
            counts[item.sector_name] = counts.get(item.sector_name, 0) + 1
    return counts


def _response_diffusion_score(
    *,
    sector_name: str,
    item_count: int,
    same_sector_limit_up_count: int,
    leader_score: float,
    hot_industries: list[str],
) -> float:
    score = min(40.0, max(item_count, 1) * 12.0)
    score += min(32.0, same_sector_limit_up_count * 24.0)
    if sector_name in hot_industries[:3]:
        score += 18.0
    if leader_score >= 75.0:
        score += 36.0
    return max(0.0, min(100.0, score))


def _sector_rank_from_response(sector_name: str, items: list[Any]) -> int | None:
    ordered = []
    for item in items:
        if item.sector_name not in ordered:
            ordered.append(item.sector_name)
    try:
        return ordered.index(sector_name) + 1
    except ValueError:
        return None


def _bounded(value: float | None, *, default: float) -> float:
    if value is None:
        return default
    return max(0.0, min(100.0, float(value)))


def _sector_leader_gate_enabled() -> bool:
    settings = get_settings()
    return bool(settings.decision_context_enabled and settings.sector_leader_gate_production_enabled)
