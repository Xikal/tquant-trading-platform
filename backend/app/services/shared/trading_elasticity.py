from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.entities import TradingElasticityCache


MISSING_ELASTICITY_SCORE = 10.0


@dataclass(frozen=True)
class TradingElasticity:
    score: float = MISSING_ELASTICITY_SCORE
    data_quality: str = "unavailable"
    tier: str = "unknown"


def get_trading_elasticity(symbol: str, *, db: Session | None = None) -> TradingElasticity:
    safe_symbol = (symbol or "").strip()
    if not safe_symbol:
        return TradingElasticity()
    if db is not None:
        return _read_elasticity(db, safe_symbol)
    with SessionLocal() as session:
        return _read_elasticity(session, safe_symbol)


def _read_elasticity(db: Session, symbol: str) -> TradingElasticity:
    row = db.execute(
        select(TradingElasticityCache)
        .where(TradingElasticityCache.symbol == symbol)
        .order_by(TradingElasticityCache.updated_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        return TradingElasticity(
            score=MISSING_ELASTICITY_SCORE,
            data_quality="unavailable",
            tier=_tier(MISSING_ELASTICITY_SCORE, "unavailable"),
        )
    quality = _normalize_quality(str(row.data_quality or ""), sample_count=int(row.sample_count or 0))
    if row.updated_at and row.updated_at < datetime.now() - timedelta(minutes=30):
        quality = "stale"
    score = float(row.elasticity_score or 0.0)
    return TradingElasticity(score=score, data_quality=quality, tier=str(row.elasticity_tier or _tier(score, quality)))


def _tier(score: float, quality: str) -> str:
    if quality != "fresh":
        return "unknown"
    if score >= 75:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def _normalize_quality(raw_value: str, *, sample_count: int) -> str:
    normalized = raw_value.strip().lower()
    if normalized in {"fresh", "stale", "estimated", "unavailable"}:
        return normalized
    if normalized == "ok":
        return "fresh" if sample_count > 0 else "estimated"
    return "estimated" if sample_count <= 0 else "fresh"
