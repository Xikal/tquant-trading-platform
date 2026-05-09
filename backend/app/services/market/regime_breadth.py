from __future__ import annotations

import logging
import threading
from typing import Any

import pandas as pd
from sqlalchemy import desc, func, select

from app.core.database import SessionLocal
from app.models.entities import DailyBarSnapshot
from app.services.market.regime_helpers import clean_hot_sequences, ranked_hot_overlap_score
from app.services.market.regime_types import MarketBreadthSnapshot


logger = logging.getLogger(__name__)


def load_market_breadth_snapshot(owner: Any, recent_hot_sequences: list[list[str]] | None = None) -> MarketBreadthSnapshot:
    sequences = recent_hot_sequences or []
    cache_key = owner._market_breadth_cache_key(sequences)
    cached = owner._get_market_breadth_cache(cache_key)
    if cached is not None:
        return cached

    snapshot_map = owner._get_spot_snapshot_cache("stock") or {}
    if not snapshot_map:
        owner._warm_market_breadth_snapshot_async(cache_key, sequences)
        local_snapshot = owner._load_local_daily_breadth_snapshot(sequences)
        if local_snapshot is not None:
            owner._set_market_breadth_cache(cache_key, local_snapshot)
            return local_snapshot
        return owner._build_market_breadth_snapshot(
            snapshot_map={},
            recent_hot_sequences=sequences,
            breadth_ready=False,
        )

    snapshot = owner._build_market_breadth_snapshot(
        snapshot_map=snapshot_map,
        recent_hot_sequences=sequences,
        breadth_ready=True,
    )
    owner._set_market_breadth_cache(cache_key, snapshot)
    return snapshot


def load_local_daily_breadth_snapshot(owner: Any, recent_hot_sequences: list[list[str]]) -> MarketBreadthSnapshot | None:
    try:
        with SessionLocal() as db:
            candidates = db.execute(
                select(DailyBarSnapshot.trade_date, func.count(DailyBarSnapshot.id).label("row_count"))
                .where(DailyBarSnapshot.instrument_type == "stock")
                .group_by(DailyBarSnapshot.trade_date)
                .order_by(desc(DailyBarSnapshot.trade_date))
                .limit(5)
            ).all()
            trade_date = next(
                (
                    row.trade_date
                    for row in candidates
                    if int(row._mapping.get("row_count") or 0) >= 1000
                ),
                None,
            )
            if not trade_date:
                return None
            rows = db.execute(
                select(DailyBarSnapshot.pct_chg).where(
                    DailyBarSnapshot.instrument_type == "stock",
                    DailyBarSnapshot.trade_date == trade_date,
                )
            ).all()
    except Exception:
        logger.exception("failed to load local daily breadth fallback")
        return None
    changes = [float(row.pct_chg or 0.0) for row in rows]
    if not changes:
        return None
    frame = pd.Series(changes, dtype="float64")
    largecap_change, smallcap_change = owner._load_style_proxy_changes()
    return MarketBreadthSnapshot(
        breadth_ready=True,
        stock_up_ratio=round(float((frame > 0).mean()), 4),
        stock_median_change=round(float(frame.median()), 4),
        largecap_change=largecap_change,
        smallcap_change=smallcap_change,
        style_divergence=round(largecap_change - smallcap_change, 4),
        hot_turnover=compute_hot_turnover(recent_hot_sequences),
        hot_overlap_ratio=compute_hot_overlap_ratio(recent_hot_sequences),
    )


def warm_market_breadth_snapshot_async(owner: Any, cache_key: str, recent_hot_sequences: list[list[str]]) -> None:
    with owner._cache_lock:
        if cache_key in owner._market_breadth_jobs:
            return
        owner._market_breadth_jobs.add(cache_key)

    def runner() -> None:
        try:
            snapshot = owner._build_market_breadth_snapshot(
                snapshot_map={},
                recent_hot_sequences=recent_hot_sequences,
                breadth_ready=False,
            )
            owner._set_market_breadth_cache(cache_key, snapshot)
        finally:
            with owner._cache_lock:
                owner._market_breadth_jobs.discard(cache_key)

    threading.Thread(target=runner, name=f"market-breadth-{cache_key}", daemon=True).start()


def build_market_breadth_snapshot(
    owner: Any,
    *,
    snapshot_map: dict[str, Any],
    recent_hot_sequences: list[list[str]],
    breadth_ready: bool,
) -> MarketBreadthSnapshot:
    changes = [item.change_pct for item in snapshot_map.values()] if snapshot_map else []
    frame = pd.Series(changes, dtype="float64") if changes else pd.Series(dtype="float64")
    stock_up_ratio = round(float((frame > 0).mean()), 4) if not frame.empty else 0.0
    stock_median_change = round(float(frame.median()), 4) if not frame.empty else 0.0
    largecap_change, smallcap_change = owner._load_style_proxy_changes()
    return MarketBreadthSnapshot(
        breadth_ready=breadth_ready,
        stock_up_ratio=stock_up_ratio,
        stock_median_change=stock_median_change,
        largecap_change=largecap_change,
        smallcap_change=smallcap_change,
        style_divergence=round(largecap_change - smallcap_change, 4),
        hot_turnover=compute_hot_turnover(recent_hot_sequences),
        hot_overlap_ratio=compute_hot_overlap_ratio(recent_hot_sequences),
    )


def compute_hot_turnover(sequences: list[list[str]]) -> float:
    cleaned = clean_hot_sequences(sequences)
    if len(cleaned) < 2:
        return 0.0
    turnovers = [1.0 - ranked_hot_overlap_score(left, right) for left, right in zip(cleaned, cleaned[1:])]
    if not turnovers:
        return 0.0
    return round(sum(turnovers) / len(turnovers), 4)


def compute_hot_overlap_ratio(sequences: list[list[str]]) -> float:
    cleaned = clean_hot_sequences(sequences)
    if len(cleaned) < 2:
        return 0.0
    latest, previous = cleaned[0], cleaned[1]
    return round(ranked_hot_overlap_score(latest, previous), 4)
