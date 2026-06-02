from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.models.entities import KeyLevelSnapshot
from app.models.schema_defs.key_levels import KeyLevelResult


class KeyLevelSnapshotRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def read(
        self,
        *,
        scope: str,
        cache_key: str,
        trade_date: str | None = None,
        engine_version: str | None = None,
    ) -> KeyLevelResult | None:
        statement = (
            select(KeyLevelSnapshot)
            .where(KeyLevelSnapshot.scope == _normalize_scope(scope))
            .where(KeyLevelSnapshot.cache_key == _normalize_cache_key(cache_key))
        )
        if trade_date:
            statement = statement.where(KeyLevelSnapshot.trade_date == str(trade_date)[:10])
        if engine_version:
            statement = statement.where(KeyLevelSnapshot.engine_version == engine_version)
        row = self.db.execute(
            statement.order_by(
                desc(KeyLevelSnapshot.trade_date),
                desc(KeyLevelSnapshot.id),
            ).limit(1)
        ).scalar_one_or_none()
        if row is None:
            return None
        payload = _json_dict(row.payload_json)
        data = payload.get("result") if isinstance(payload.get("result"), dict) else payload
        if not isinstance(data, dict):
            return None
        return KeyLevelResult.model_validate(data)

    def upsert(self, result: KeyLevelResult, *, cache_key: str | None = None) -> None:
        normalized_key = _normalize_cache_key(cache_key or result.symbol)
        normalized_scope = _normalize_scope(result.scope)
        trade_date = str(result.trade_date)[:10]
        engine_version = str(result.engine_version or "akey-level-v1")
        payload = _json_dumps(
            {
                "scope": normalized_scope,
                "cache_key": normalized_key,
                "symbol": result.symbol,
                "trade_date": trade_date,
                "engine_version": engine_version,
                "data_quality": result.data_quality,
                "result": result.model_dump(mode="json"),
            }
        )
        row = self.db.execute(
            select(KeyLevelSnapshot)
            .where(KeyLevelSnapshot.scope == normalized_scope)
            .where(KeyLevelSnapshot.cache_key == normalized_key)
            .where(KeyLevelSnapshot.trade_date == trade_date)
            .where(KeyLevelSnapshot.engine_version == engine_version)
        ).scalar_one_or_none()
        if row is None:
            self.db.add(
                KeyLevelSnapshot(
                    scope=normalized_scope,
                    cache_key=normalized_key,
                    symbol=str(result.symbol or normalized_key),
                    trade_date=trade_date,
                    engine_version=engine_version,
                    data_quality=str(result.data_quality),
                    payload_json=payload,
                )
            )
            return
        row.symbol = str(result.symbol or normalized_key)
        row.data_quality = str(result.data_quality)
        row.payload_json = payload

    def cleanup_old_trade_dates(self, *, keep_trade_dates: int = 5) -> int:
        keep_count = max(1, int(keep_trade_dates or 1))
        trade_dates = [
            str(row)
            for row in self.db.execute(
                select(KeyLevelSnapshot.trade_date)
                .distinct()
                .order_by(desc(KeyLevelSnapshot.trade_date))
                .limit(keep_count)
            ).scalars()
        ]
        if not trade_dates:
            return 0
        result = self.db.execute(
            delete(KeyLevelSnapshot).where(~KeyLevelSnapshot.trade_date.in_(trade_dates))
        )
        return int(result.rowcount or 0)


def _normalize_scope(scope: str) -> str:
    return str(scope or "").strip() or "stock"


def _normalize_cache_key(cache_key: str) -> str:
    text = str(cache_key or "").strip()
    return text or "market"


def _json_dumps(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _json_dict(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}
