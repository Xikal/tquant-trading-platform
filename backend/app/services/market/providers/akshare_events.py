from __future__ import annotations

from app.core.timezone import beijing_now
from app.models.schemas import MarketEventOut
from app.services.market.shared import ak


def fetch_notice_events(raw_call, symbol: str) -> list[MarketEventOut]:  # noqa: ANN001
    today = beijing_now().strftime("%Y%m%d")
    categories = ("风险提示", "重大事项", "持股变动")
    hits: list[MarketEventOut] = []
    for category in categories:
        try:
            frame = raw_call(
                ak.stock_notice_report,
                symbol=category,
                date=today,
                purpose="notice",
            )
        except Exception:
            continue
        if frame is None or getattr(frame, "empty", True):
            continue
        matched = frame[frame["代码"].astype(str) == symbol] if "代码" in frame else frame.iloc[0:0]
        for _, row in matched.head(3).iterrows():
            risk_level = "high" if category in {"风险提示", "重大事项"} else "medium"
            hits.append(
                MarketEventOut(
                    title=str(row.get("公告标题", "相关公告")),
                    risk_level=risk_level,
                    description=f"{category}公告，需确认是否影响盘中波动与流动性。",
                    source="notice",
                    event_time=str(row.get("公告日期", "")),
                )
            )
    return hits


def fetch_news_events(raw_call, symbol: str) -> list[MarketEventOut]:  # noqa: ANN001
    try:
        frame = raw_call(ak.stock_news_em, symbol=symbol, purpose="news")
    except Exception:
        return []
    if frame is None or getattr(frame, "empty", True):
        return []
    risk_keywords = {
        "停牌": "high",
        "问询": "high",
        "立案": "high",
        "风险提示": "high",
        "减持": "medium",
        "诉讼": "high",
        "异常波动": "medium",
        "预亏": "high",
        "预减": "high",
        "回购": "low",
        "增持": "low",
        "中标": "low",
    }
    events: list[MarketEventOut] = []
    for _, row in frame.head(8).iterrows():
        text = f"{row.get('新闻标题', '')} {row.get('新闻内容', '')}"
        matched_level = next((level for keyword, level in risk_keywords.items() if keyword in text), None)
        if matched_level:
            events.append(
                MarketEventOut(
                    title=str(row.get("新闻标题", "相关新闻")),
                    risk_level=matched_level,
                    description=str(row.get("新闻内容", ""))[:120],
                    source="news",
                    event_time=str(row.get("发布时间", "")),
                )
            )
    return events
