from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.services.trading_experience import repository
from app.services.trading_experience.schemas import RelativeStrengthItem


def build_board(db: Session, *, trade_date: date | None = None, limit: int = 30) -> list[RelativeStrengthItem]:
    target = trade_date or repository.latest_trade_date(db)
    if not target:
        return []
    rows = repository.daily_rows_for_date(db, target, limit=500)
    if not rows:
        return []
    market_pct = sum(float(row.pct_chg or 0.0) for row, _, _ in rows) / len(rows)
    sector_pct: dict[str, float] = {}
    sector_counts: dict[str, int] = {}
    for row, _, sector in rows:
        key = str(sector or "unknown")
        sector_pct[key] = sector_pct.get(key, 0.0) + float(row.pct_chg or 0.0)
        sector_counts[key] = sector_counts.get(key, 0) + 1
    sector_avg = {key: value / sector_counts[key] for key, value in sector_pct.items()}
    as_of = datetime.now()
    items: list[RelativeStrengthItem] = []
    ranked = sorted(rows, key=lambda item: (float(item[0].pct_chg or 0.0) - market_pct, float(item[0].amount or 0.0)), reverse=True)
    for index, (row, _, sector) in enumerate(ranked[:limit], start=1):
        stock_pct = float(row.pct_chg or 0.0)
        sector_key = str(sector or "unknown")
        sec_pct = sector_avg.get(sector_key, market_pct)
        items.append(
            RelativeStrengthItem(
                symbol=row.symbol,
                trade_date=target.isoformat(),
                index_code="market_average",
                sector_code=sector_key,
                stock_pct=round(stock_pct, 4),
                index_pct=round(market_pct, 4),
                sector_pct=round(sec_pct, 4),
                rs_vs_index=round(stock_pct - market_pct, 4),
                rs_vs_sector=round(stock_pct - sec_pct, 4),
                sector_rank=index,
                resilience_flag=_flag(stock_pct, market_pct, sec_pct),
                data_quality="ok" if row.data_quality == "ok" else "insufficient",
                as_of=as_of,
            )
        )
    return items


def _flag(stock_pct: float, index_pct: float, sector_pct: float) -> str:
    if index_pct <= -1.0 and stock_pct > index_pct + 2.0 and stock_pct >= sector_pct:
        return "resilient"
    if stock_pct < index_pct - 1.0:
        return "follow_down"
    return "neutral"
