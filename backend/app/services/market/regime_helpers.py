from __future__ import annotations

from dataclasses import fields
import json

from app.services.market.regime_types import MarketRegimeSnapshot

_SNAPSHOT_FIELD_NAMES = {field.name for field in fields(MarketRegimeSnapshot)}


def transition_risk(snapshot: MarketRegimeSnapshot, previous_snapshot: MarketRegimeSnapshot) -> float:
    state_changed = snapshot.state != previous_snapshot.state
    score_gap = abs(snapshot.regime_score - previous_snapshot.regime_score)
    strength_gap = abs(snapshot.state_strength - previous_snapshot.state_strength)
    raw = (0.40 if state_changed else 0.08) + min(score_gap / 40.0, 0.35) + min(strength_gap, 0.25)
    if snapshot.hot_turnover >= 0.65:
        raw += 0.12
    if snapshot.distribution_pressure >= 55.0:
        raw += 0.10
    return round(max(0.0, min(1.0, raw)), 4)


def clean_hot_sequences(sequences: list[list[str]]) -> list[list[str]]:
    cleaned: list[list[str]] = []
    for sequence in sequences:
        row = [item.strip() for item in sequence if item and item.strip()]
        if row:
            cleaned.append(row[:3])
    return cleaned


def ranked_hot_overlap_score(latest: list[str], previous: list[str]) -> float:
    if not latest or not previous:
        return 0.0
    latest_top = latest[:3]
    previous_top = previous[:3]
    latest_set = set(latest_top)
    previous_set = set(previous_top)
    common = latest_set & previous_set
    set_score = len(common) / max(len(latest_set | previous_set), 1)
    top1_score = 1.0 if latest_top[0] == previous_top[0] else 0.0
    rank_score = rank_continuity_score(latest_top, previous_top, common)
    return round(top1_score * 0.36 + set_score * 0.44 + rank_score * 0.20, 4)


def rank_continuity_score(latest: list[str], previous: list[str], common: set[str]) -> float:
    if not common:
        return 0.0
    latest_rank = {industry: index for index, industry in enumerate(latest)}
    previous_rank = {industry: index for index, industry in enumerate(previous)}
    scores = [
        max(0.0, 1.0 - abs(latest_rank[industry] - previous_rank[industry]) / 3.0)
        for industry in common
    ]
    return sum(scores) / len(scores)


def snapshot_from_payload(raw_payload: str | None) -> MarketRegimeSnapshot | None:
    try:
        payload = json.loads(raw_payload or "{}")
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    filtered = {key: value for key, value in payload.items() if key in _SNAPSHOT_FIELD_NAMES}
    try:
        return MarketRegimeSnapshot(**filtered)
    except TypeError:
        return None


def regime_data_quality(snapshot: MarketRegimeSnapshot) -> str:
    if snapshot.breadth_ready and snapshot.emotion_ready and snapshot.hot_industry_source not in {
        "cached_fallback",
        "unavailable",
        "fallback",
        "none",
    }:
        return "ok"
    if snapshot.breadth_ready or snapshot.emotion_ready:
        return "partial"
    return "limited"
