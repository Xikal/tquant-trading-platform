from __future__ import annotations

import json
import logging

from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.models.entities import LowBuyResultSnapshot, LowBuyScanSnapshot
from app.services.low_buy.shared import LOW_BUY_RESULT_VERSION

logger = logging.getLogger(__name__)


def cleanup_stale_low_buy_snapshots() -> None:
    """Remove materialized low-buy rows produced by older strategy versions."""

    with SessionLocal() as db:
        result_ids = _stale_low_buy_result_ids(db)
        scan_ids = _stale_low_buy_scan_ids(db)
        if result_ids:
            _delete_low_buy_rows(db, LowBuyResultSnapshot, result_ids)
        if scan_ids:
            _delete_low_buy_rows(db, LowBuyScanSnapshot, scan_ids)
        db.commit()
    if result_ids or scan_ids:
        logger.info(
            "cleaned stale low-buy snapshots: %d results + %d scans removed",
            len(result_ids),
            len(scan_ids),
        )


def _stale_low_buy_result_ids(db) -> list[int]:
    return _stale_snapshot_ids(
        db=db,
        model=LowBuyResultSnapshot,
        json_column=LowBuyResultSnapshot.payload_json,
        version_key="payload_version",
    )


def _stale_low_buy_scan_ids(db) -> list[int]:
    return _stale_snapshot_ids(
        db=db,
        model=LowBuyScanSnapshot,
        json_column=LowBuyScanSnapshot.filters_json,
        version_key="_result_version",
    )


def _stale_snapshot_ids(db, model, json_column, version_key: str, batch_size: int = 1000) -> list[int]:
    stale_ids: list[int] = []
    last_id = 0
    while True:
        rows = db.execute(
            select(model.id, json_column)
            .where(model.id > last_id)
            .order_by(model.id.asc())
            .limit(batch_size)
        ).all()
        if not rows:
            break
        last_id = int(rows[-1][0])
        stale_ids.extend(
            int(row_id)
            for row_id, raw_json in rows
            if _json_version(raw_json, version_key) != LOW_BUY_RESULT_VERSION
        )
    return stale_ids


def _delete_low_buy_rows(db, model, row_ids: list[int]) -> None:
    for index in range(0, len(row_ids), 500):
        chunk = row_ids[index : index + 500]
        db.execute(delete(model).where(model.id.in_(chunk)))


def _json_version(raw: str | None, key: str) -> int | None:
    try:
        payload = json.loads(raw or "{}")
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    value = payload.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None
