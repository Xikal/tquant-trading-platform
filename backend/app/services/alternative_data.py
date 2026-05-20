from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_now
from app.models.entities import MarketEventCache

POSITIVE_WORDS = ("增持", "回购", "中标", "订单", "增长", "突破", "涨停", "净流入", "利好", "合作")
NEGATIVE_WORDS = ("减持", "处罚", "亏损", "问询", "暴跌", "风险", "退市", "净流出", "利空", "诉讼")


class AlternativeDataSentimentService:
    """Research-only news/event sentiment based on cached provider events."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def build(self, *, symbols: list[str] | None = None, limit: int = 80) -> dict[str, Any]:
        rows = self._events(symbols=symbols, limit=max(1, min(limit, 300)))
        by_symbol: dict[str, list[MarketEventCache]] = {}
        for row in rows:
            by_symbol.setdefault(row.symbol, []).append(row)
        items = [_symbol_item(symbol, events) for symbol, events in sorted(by_symbol.items())]
        return {
            "generated_at": beijing_now().isoformat(timespec="seconds"),
            "mode": "research_only",
            "source": "market_events_cache",
            "items": items,
            "summary": _summary(items),
            "notes": [
                "另类数据情绪仅使用已缓存新闻/公告事件，不直接触发自动交易。",
                "未接入付费舆情源时，缺失股票会显示为 unavailable。",
            ],
        }

    def _events(self, *, symbols: list[str] | None, limit: int) -> list[MarketEventCache]:
        statement = select(MarketEventCache).order_by(MarketEventCache.created_at.desc()).limit(limit)
        clean_symbols = [symbol.strip() for symbol in symbols or [] if symbol.strip()]
        if clean_symbols:
            statement = statement.where(MarketEventCache.symbol.in_(clean_symbols))
        return list(self.db.execute(statement).scalars().all())


def _symbol_item(symbol: str, events: list[MarketEventCache]) -> dict[str, Any]:
    scores = [_event_score(event) for event in events]
    total = sum(scores)
    label = "neutral"
    if total >= 2:
        label = "positive"
    elif total <= -2:
        label = "negative"
    sources = Counter(str(event.source or "unknown") for event in events)
    return {
        "symbol": symbol,
        "event_count": len(events),
        "sentiment_score": int(total),
        "sentiment_label": label,
        "source_mix": dict(sources),
        "latest_events": [
            {
                "title": event.title,
                "risk_level": event.risk_level,
                "source": event.source,
                "event_time": event.event_time,
                "score": _event_score(event),
            }
            for event in events[:5]
        ],
    }


def _event_score(event: MarketEventCache) -> int:
    text = f"{event.title} {event.description}"
    positive = sum(1 for word in POSITIVE_WORDS if word in text)
    negative = sum(1 for word in NEGATIVE_WORDS if word in text)
    if str(event.risk_level or "").lower() == "high":
        negative += 1
    return max(-3, min(3, positive - negative))


def _summary(items: list[dict[str, Any]]) -> str:
    if not items:
        return "暂无缓存新闻/公告事件，另类数据情绪不可用。"
    positives = sum(1 for item in items if item["sentiment_label"] == "positive")
    negatives = sum(1 for item in items if item["sentiment_label"] == "negative")
    return f"覆盖 {len(items)} 只股票：正面 {positives}，负面 {negatives}。"
