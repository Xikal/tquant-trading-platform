from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import MarketEventCache


EVENT_CACHE_FRESH_DAYS = 7


@dataclass(frozen=True)
class CachedMarketEvents:
    symbol: str
    events: list[dict[str, Any]]
    data_quality: str
    reasons: list[str]


def load_cached_market_events(
    db: Session,
    *,
    symbol: str,
    limit: int = 8,
    max_age_days: int = EVENT_CACHE_FRESH_DAYS,
) -> CachedMarketEvents:
    safe_limit = max(1, min(int(limit or 8), 20))
    rows = (
        db.execute(
            select(MarketEventCache)
            .where(MarketEventCache.symbol == symbol)
            .order_by(MarketEventCache.created_at.desc(), MarketEventCache.id.desc())
            .limit(safe_limit)
        )
        .scalars()
        .all()
    )
    if not rows:
        return CachedMarketEvents(
            symbol=symbol,
            events=[],
            data_quality="missing",
            reasons=["公告/事件源缺失，不能把无事件解释为安全。"],
        )
    freshest = max((row.created_at for row in rows if row.created_at), default=None)
    if freshest is None or freshest < datetime.utcnow() - timedelta(days=max(1, int(max_age_days or EVENT_CACHE_FRESH_DAYS))):
        return CachedMarketEvents(
            symbol=symbol,
            events=[],
            data_quality="missing",
            reasons=["公告/事件缓存陈旧或过期，事件风险只做 missing 展示，不阻断生产。"],
        )
    return CachedMarketEvents(
        symbol=symbol,
        events=[
            {
                "id": int(row.id),
                "title": row.title,
                "risk_level": row.risk_level,
                "description": row.description,
                "source": row.source,
                "event_time": row.event_time,
                "created_at": row.created_at.isoformat() if row.created_at else "",
            }
            for row in rows
        ],
        data_quality="ok",
        reasons=[],
    )
