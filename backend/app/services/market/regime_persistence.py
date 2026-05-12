from __future__ import annotations

import json
import logging
from dataclasses import asdict, replace

from sqlalchemy import desc, select
from sqlalchemy.exc import OperationalError

from app.core.database import SessionLocal
from app.models.entities import MarketRegimeSnapshotCache
from app.services.market.regime_helpers import regime_data_quality, snapshot_from_payload
from app.services.market.regime_types import MarketRegimeSnapshot
from app.services.shared.distributed_cache import get_json_cache, set_json_cache

logger = logging.getLogger(__name__)


def persist_market_regime_snapshot(key: str, snapshot: MarketRegimeSnapshot) -> None:
    try:
        payload = json.dumps(asdict(snapshot), ensure_ascii=False)
        set_json_cache(_cache_key(key), {"trade_date": key, "payload": asdict(snapshot)}, ttl_seconds=180)
        with SessionLocal() as db:
            row = db.execute(
                select(MarketRegimeSnapshotCache).where(MarketRegimeSnapshotCache.cache_key == key)
            ).scalar_one_or_none()
            if row is None:
                row = MarketRegimeSnapshotCache(cache_key=key)
                db.add(row)
            row.trade_date = key
            row.state = snapshot.state
            row.breadth_ready = bool(snapshot.breadth_ready)
            row.emotion_ready = bool(snapshot.emotion_ready)
            row.hot_industry_source = snapshot.hot_industry_source
            row.data_quality = regime_data_quality(snapshot)
            row.payload_json = payload
            db.commit()
    except Exception:
        logger.exception("failed to persist market regime snapshot")


def load_persisted_market_regime_snapshot(
    key: str,
    hot_industries: list[str] | None,
) -> MarketRegimeSnapshot | None:
    trade_date = ""
    cached = _load_distributed_snapshot(key)
    if cached is not None and _snapshot_industries_match(cached, hot_industries):
        return replace(
            cached,
            snapshot_source="cached",
            snapshot_source_text=f"使用 {key} 跨进程市场快照，后台正在刷新实时情绪",
        )
    try:
        with SessionLocal() as db:
            row = db.execute(
                select(MarketRegimeSnapshotCache).where(MarketRegimeSnapshotCache.cache_key == key)
            ).scalar_one_or_none()
            if row is not None and not (row.breadth_ready or row.emotion_ready):
                row = None
            if row is None:
                row = db.execute(
                    select(MarketRegimeSnapshotCache)
                    .where(MarketRegimeSnapshotCache.breadth_ready.is_(True))
                    .order_by(desc(MarketRegimeSnapshotCache.trade_date), desc(MarketRegimeSnapshotCache.updated_at))
                    .limit(1)
                ).scalar_one_or_none()
            if row is None:
                return None
            trade_date = str(row.trade_date or "")
            snapshot = snapshot_from_payload(row.payload_json)
            if snapshot is not None:
                set_json_cache(_cache_key(key), {"trade_date": trade_date, "payload": asdict(snapshot)}, ttl_seconds=180)
    except OperationalError as exc:
        if "no such table" not in str(exc).lower():
            logger.exception("failed to load persisted market regime snapshot")
        return None
    except Exception:
        logger.exception("failed to load persisted market regime snapshot")
        return None
    if snapshot is None:
        return None
    if not _snapshot_industries_match(snapshot, hot_industries):
        return None
    return replace(
        snapshot,
        snapshot_source="cached",
        snapshot_source_text=f"使用 {trade_date} 最近完整市场快照，后台正在刷新实时情绪",
    )


def _cache_key(key: str) -> str:
    return f"tquant:market-regime:{key}"


def _load_distributed_snapshot(key: str) -> MarketRegimeSnapshot | None:
    cached = get_json_cache(_cache_key(key))
    if not isinstance(cached, dict):
        return None
    payload = cached.get("payload")
    if not isinstance(payload, dict):
        return None
    return snapshot_from_payload(json.dumps(payload, ensure_ascii=False))


def _snapshot_industries_match(snapshot: MarketRegimeSnapshot, hot_industries: list[str] | None) -> bool:
    return not (hot_industries and snapshot.hot_industries and hot_industries != snapshot.hot_industries)
