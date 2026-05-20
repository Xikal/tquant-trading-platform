from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import median
import threading
import time

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_now_string
from app.models.entities import DailyBarSnapshot, Instrument
from app.models.schema_defs.market import SectorRelativeStrengthItem, SectorRelativeStrengthResponse

_CACHE_LOCK = threading.Lock()
_CACHE_TTL_SECONDS = 60.0
_CACHE: dict[str, tuple[float, SectorRelativeStrengthResponse]] = {}


@dataclass(frozen=True)
class LeaderStrengthLookup:
    score_by_symbol: dict[str, float]
    rank_by_symbol: dict[str, int]
    text_by_symbol: dict[str, str]


def build_sector_relative_strength_rank(
    db: Session,
    *,
    hot_sectors: list[str] | None = None,
    sector_limit: int = 8,
    per_sector_limit: int = 10,
    trade_date: str = "",
) -> SectorRelativeStrengthResponse:
    target_date = trade_date or _latest_complete_trade_date(db)
    if not target_date:
        return SectorRelativeStrengthResponse(updated_at=beijing_now_string(), notes=["暂无完整日线快照，无法计算板块内相对强度。"])
    cache_key = _cache_key(target_date, hot_sectors or [], sector_limit, per_sector_limit)
    cached = _read_cache(cache_key)
    if cached is not None:
        return cached
    rows = _load_current_rows(db, target_date)
    if not rows:
        return SectorRelativeStrengthResponse(updated_at=beijing_now_string(), trade_date=target_date, notes=["暂无行业映射或日线数据。"])
    sectors = _select_sectors(rows, hot_sectors or [], sector_limit)
    previous_volume = _previous_average_volume(db, target_date, [row["symbol"] for row in rows])
    items: list[SectorRelativeStrengthItem] = []
    for sector_name in sectors:
        sector_rows = [row for row in rows if row["sector_name"] == sector_name]
        if not sector_rows:
            continue
        sector_median = median([row["change_pct"] for row in sector_rows])
        sector_amount_median = max(median([max(row["amount"], 0.0) for row in sector_rows]), 1.0)
        ranked: list[SectorRelativeStrengthItem] = []
        for row in sector_rows:
            avg_volume = previous_volume.get(row["symbol"], 0.0)
            volume_ratio = row["volume"] / avg_volume if avg_volume > 0 else 0.0
            turnover_proxy = row["amount"] / sector_amount_median if sector_amount_median > 0 else 0.0
            leader_score = _leader_score(row["change_pct"], sector_median, volume_ratio, turnover_proxy)
            ranked.append(
                SectorRelativeStrengthItem(
                    sector_name=sector_name,
                    symbol=row["symbol"],
                    name=row["name"],
                    latest_price=row["close_price"],
                    change_pct=row["change_pct"],
                    sector_median_change_pct=round(sector_median, 4),
                    relative_strength_ratio=_relative_ratio(row["change_pct"], sector_median),
                    volume_ratio=round(volume_ratio, 4),
                    turnover_proxy=round(turnover_proxy, 4),
                    leader_score=leader_score,
                    data_quality_text="换手率缺少稳定免费字段，当前以成交额行业中位数代理。",
                )
            )
        ranked.sort(key=lambda item: item.leader_score, reverse=True)
        for index, item in enumerate(ranked[: max(1, per_sector_limit)], start=1):
            items.append(item.model_copy(update={"rank": index}))
    response = SectorRelativeStrengthResponse(
        updated_at=beijing_now_string(),
        trade_date=target_date,
        sector_count=len(sectors),
        items=items,
        notes=["龙头分 = 行业内超额涨幅 + 量比 + 成交额代理；仅用于排序加权，不单独构成买入信号。"],
    )
    _write_cache(cache_key, response)
    return response


def _cache_key(target_date: str, hot_sectors: list[str], sector_limit: int, per_sector_limit: int) -> str:
    sectors = ",".join(sorted(item for item in hot_sectors if item))
    return f"{target_date}|{sector_limit}|{per_sector_limit}|{sectors}"


def _read_cache(cache_key: str) -> SectorRelativeStrengthResponse | None:
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(cache_key)
        if not cached:
            return None
        expires_at, response = cached
        if expires_at <= now:
            _CACHE.pop(cache_key, None)
            return None
        return response


def _write_cache(cache_key: str, response: SectorRelativeStrengthResponse) -> None:
    with _CACHE_LOCK:
        _CACHE[cache_key] = (time.monotonic() + _CACHE_TTL_SECONDS, response)


def build_leader_strength_lookup(response: SectorRelativeStrengthResponse) -> LeaderStrengthLookup:
    score_by_symbol: dict[str, float] = {}
    rank_by_symbol: dict[str, int] = {}
    text_by_symbol: dict[str, str] = {}
    for item in response.items:
        score_by_symbol[item.symbol] = float(item.leader_score or 0.0)
        rank_by_symbol[item.symbol] = int(item.rank or 0)
        text_by_symbol[item.symbol] = f"{item.sector_name} 板块内第 {item.rank}，龙头分 {item.leader_score:.1f}"
    return LeaderStrengthLookup(score_by_symbol=score_by_symbol, rank_by_symbol=rank_by_symbol, text_by_symbol=text_by_symbol)


def _latest_complete_trade_date(db: Session) -> str:
    rows = db.execute(
        select(DailyBarSnapshot.trade_date, func.count(DailyBarSnapshot.symbol).label("stock_count"))
        .where(DailyBarSnapshot.instrument_type == "stock")
        .group_by(DailyBarSnapshot.trade_date)
        .having(func.count(DailyBarSnapshot.symbol) >= 3000)
        .order_by(desc(DailyBarSnapshot.trade_date))
        .limit(1)
    ).all()
    return str(rows[0][0]) if rows else ""


def _load_current_rows(db: Session, trade_date: str) -> list[dict[str, object]]:
    statement = (
        select(
            DailyBarSnapshot.symbol,
            Instrument.name,
            Instrument.sector_name,
            DailyBarSnapshot.close_price,
            DailyBarSnapshot.pct_chg,
            DailyBarSnapshot.volume,
            DailyBarSnapshot.amount,
        )
        .join(Instrument, Instrument.symbol == DailyBarSnapshot.symbol)
        .where(
            DailyBarSnapshot.trade_date == trade_date,
            DailyBarSnapshot.instrument_type == "stock",
            Instrument.sector_name.isnot(None),
        )
    )
    result = []
    for symbol, name, sector_name, close_price, pct_chg, volume, amount in db.execute(statement).all():
        sector = str(sector_name or "").strip()
        if not sector:
            continue
        result.append(
            {
                "symbol": str(symbol),
                "name": str(name or symbol),
                "sector_name": sector,
                "close_price": float(close_price or 0.0),
                "change_pct": float(pct_chg or 0.0),
                "volume": float(volume or 0.0),
                "amount": float(amount or 0.0),
            }
        )
    return result


def _select_sectors(rows: list[dict[str, object]], hot_sectors: list[str], limit: int) -> list[str]:
    available = {str(row["sector_name"]) for row in rows}
    selected = [sector for sector in hot_sectors if sector in available]
    if len(selected) >= limit:
        return selected[:limit]
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[str(row["sector_name"])].append(float(row["change_pct"] or 0.0))
    ranked = sorted(grouped.items(), key=lambda item: median(item[1]), reverse=True)
    for sector, _values in ranked:
        if sector not in selected:
            selected.append(sector)
        if len(selected) >= limit:
            break
    return selected


def _previous_average_volume(db: Session, trade_date: str, symbols: list[str]) -> dict[str, float]:
    if not symbols:
        return {}
    dates = [
        str(item)
        for item in db.execute(
            select(DailyBarSnapshot.trade_date)
            .where(DailyBarSnapshot.trade_date < trade_date)
            .group_by(DailyBarSnapshot.trade_date)
            .order_by(desc(DailyBarSnapshot.trade_date))
            .limit(5)
        ).scalars()
    ]
    if not dates:
        return {}
    volumes: dict[str, list[float]] = defaultdict(list)
    for symbol, volume in db.execute(
        select(DailyBarSnapshot.symbol, DailyBarSnapshot.volume).where(
            DailyBarSnapshot.trade_date.in_(dates),
            DailyBarSnapshot.symbol.in_(symbols),
        )
    ).all():
        volumes[str(symbol)].append(float(volume or 0.0))
    return {symbol: sum(values) / len(values) for symbol, values in volumes.items() if values}


def _leader_score(change_pct: float, sector_median: float, volume_ratio: float, turnover_proxy: float) -> float:
    excess_score = 50.0 + (change_pct - sector_median) * 6.0
    volume_score = min(max(volume_ratio - 1.0, 0.0), 3.0) * 10.0
    turnover_score = min(max(turnover_proxy - 1.0, 0.0), 3.0) * 5.0
    return round(max(0.0, min(100.0, excess_score + volume_score + turnover_score)), 2)


def _relative_ratio(change_pct: float, sector_median: float) -> float | None:
    if abs(sector_median) < 0.1:
        return None
    return round(change_pct / sector_median, 4)
