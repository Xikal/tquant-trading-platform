from __future__ import annotations

import json
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models.entities import TradingExperienceReviewPoolItem
from app.services.trading_experience import repository
from app.services.trading_experience.config import ENGINE_VERSION, REVIEW_POOL_DROPPED_PCT, REVIEW_POOL_MIN_PCT, REVIEW_POOL_RETAINED_PCT
from app.services.trading_experience.schemas import BoardFilter, ReviewPoolItem


def build_review_pool(
    db: Session,
    *,
    pool_date: date | None = None,
    limit: int = 30,
    persist: bool = False,
    board_filter: BoardFilter = "include_all",
) -> list[ReviewPoolItem]:
    target_date = pool_date or repository.latest_trade_date(db)
    if not target_date:
        return []
    rows = repository.daily_rows_for_date(db, target_date, limit=max(limit * 4, 80), board_filter=board_filter)
    result: list[ReviewPoolItem] = []
    as_of = datetime.now()
    for daily, name, sector in rows:
        board_type, board_name = _board_for_symbol(daily.symbol)
        if board_filter == "main_only" and board_type != "main":
            continue
        pct = float(daily.pct_chg or 0.0)
        if pct < REVIEW_POOL_MIN_PCT:
            continue
        history = repository.symbol_history(db, daily.symbol, end_date=target_date, days=6)
        volume_ratio = _volume_ratio(history)
        next_rows = repository.next_symbol_rows(db, daily.symbol, target_date, days=3)
        status, drop_reason = _retention_state(next_rows)
        evidence = [
            f"信号日涨幅 {pct:.2f}%",
            f"近五日量比 {volume_ratio:.2f}",
            f"后续跟踪 {len(next_rows)} 日，仅用于复盘",
        ]
        item = ReviewPoolItem(
            pool_date=target_date.isoformat(),
            symbol=daily.symbol,
            name=name or "",
            board_type=board_type,
            board_name=board_name,
            status=status,
            entry_pct=round(pct, 4),
            volume_ratio=round(volume_ratio, 4),
            mainline_state="sector_known" if sector else "unknown",
            sector_role=str(sector or "unknown"),
            drop_reason=drop_reason,
            tracked_days=len(next_rows),
            evidence=evidence,
            data_quality="ok" if daily.data_quality == "ok" else "insufficient",
            as_of=as_of,
            engine_version=ENGINE_VERSION,
        )
        result.append(item)
        if persist:
            repository.upsert_review_pool_item(db, _to_entity(item))
        if len(result) >= limit:
            break
    if persist:
        db.commit()
    return result


def list_review_pool(
    db: Session,
    *,
    pool_date: date | None = None,
    limit: int = 30,
    board_filter: BoardFilter = "include_all",
) -> list[ReviewPoolItem]:
    target_date = pool_date or repository.latest_trade_date(db)
    if not target_date:
        return []
    if board_filter == "include_all":
        stored = repository.stored_review_pool(db, target_date, limit=limit)
        if stored:
            return [_from_entity(row) for row in stored]
    return build_review_pool(db, pool_date=target_date, limit=limit, persist=False, board_filter=board_filter)


def _volume_ratio(history: list[object]) -> float:
    if len(history) < 2:
        return 0.0
    current = float(getattr(history[-1], "volume", 0.0) or 0.0)
    prior = [float(getattr(row, "volume", 0.0) or 0.0) for row in history[:-1] if float(getattr(row, "volume", 0.0) or 0.0) > 0]
    if not prior:
        return 0.0
    return current / (sum(prior) / len(prior))


def _retention_state(rows: list[object]) -> tuple[str, str]:
    if not rows:
        return "in_pool", ""
    worst = min(float(getattr(row, "pct_chg", 0.0) or 0.0) for row in rows)
    best = max(float(getattr(row, "pct_chg", 0.0) or 0.0) for row in rows)
    if worst <= REVIEW_POOL_DROPPED_PCT:
        return "dropped", f"跟踪期最大单日回撤 {worst:.2f}%"
    if best >= REVIEW_POOL_RETAINED_PCT:
        return "retained", ""
    return "in_pool", ""


def _board_for_symbol(symbol: str) -> tuple[str, str]:
    normalized = symbol.strip()
    if normalized.startswith(("300", "301")):
        return "chinext", "创业板"
    if normalized.startswith(("688", "689")):
        return "star", "科创板"
    if normalized.startswith(("8", "4", "920")):
        return "bse", "北交所"
    if normalized.startswith(("60", "00")):
        return "main", "主板"
    return "unknown", "未知"


def _to_entity(item: ReviewPoolItem) -> TradingExperienceReviewPoolItem:
    return TradingExperienceReviewPoolItem(
        pool_date=date.fromisoformat(item.pool_date),
        symbol=item.symbol,
        name=item.name,
        status=item.status,
        entry_pct=item.entry_pct,
        volume_ratio=item.volume_ratio,
        mainline_state=item.mainline_state,
        sector_role=item.sector_role,
        drop_reason=item.drop_reason,
        tracked_days=item.tracked_days,
        evidence_json=json.dumps(item.evidence, ensure_ascii=False),
        data_quality=item.data_quality,
        as_of=item.as_of,
        engine_version=item.engine_version,
        payload_json="{}",
    )


def _from_entity(row: TradingExperienceReviewPoolItem) -> ReviewPoolItem:
    return ReviewPoolItem(
        pool_date=row.pool_date.isoformat(),
        symbol=row.symbol,
        name=row.name,
        board_type=_board_for_symbol(row.symbol)[0],
        board_name=_board_for_symbol(row.symbol)[1],
        status=row.status,
        entry_pct=row.entry_pct,
        volume_ratio=row.volume_ratio,
        mainline_state=row.mainline_state,
        sector_role=row.sector_role,
        drop_reason=row.drop_reason,
        tracked_days=row.tracked_days,
        evidence=repository.json_list(row.evidence_json),
        data_quality=row.data_quality,
        as_of=row.as_of,
        engine_version=row.engine_version,
    )
