from __future__ import annotations

import json
import threading
import time
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.entities import SystemSetting
from app.services.shared.distributed_cache import get_json_cache, set_json_cache


_VALUE_PREFIX = "factor_mining.values."
_ACTIVE_PREFIX = "factor_mining.active."
_LOCAL_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_LOCAL_CACHE_TTL = 30.0
_LOCK = threading.Lock()


def store_latest_factor_values(db: Session, factor_key: str, values: pd.DataFrame | None) -> None:
    if values is None or values.empty:
        return
    frame = values.dropna(subset=["factor_value"]).sort_values(["symbol", "trade_date"])
    if frame.empty:
        return
    latest = frame.groupby("symbol", sort=False).tail(1)
    payload = {
        "factor_key": factor_key,
        "updated_at": int(time.time()),
        "values": {
            str(row.symbol): {"trade_date": str(row.trade_date), "value": float(row.factor_value)}
            for row in latest.itertuples(index=False)
        },
    }
    set_json_cache(_value_cache_key(factor_key), payload, ttl_seconds=7 * 24 * 3600)
    _upsert_setting(db, f"{_VALUE_PREFIX}{factor_key}", json.dumps(payload, ensure_ascii=False))
    with _LOCK:
        _LOCAL_CACHE[factor_key] = (time.monotonic() + _LOCAL_CACHE_TTL, payload)


def set_factor_active(db: Session, factor_key: str, active: bool) -> None:
    _upsert_setting(db, f"{_ACTIVE_PREFIX}{factor_key}", "true" if active else "false")
    with _LOCK:
        _LOCAL_CACHE.pop(f"active:{factor_key}", None)


def is_factor_active(factor_key: str) -> bool:
    cache_key = f"active:{factor_key}"
    cached = _local_get(cache_key)
    if cached is not None:
        return bool(cached.get("active"))
    value = _load_setting_value(f"{_ACTIVE_PREFIX}{factor_key}")
    active = str(value or "").strip().lower() in {"1", "true", "yes", "on"}
    _local_set(cache_key, {"active": active})
    return active


def read_factor_value(factor_key: str, symbol: str, trade_date: str = "") -> float:
    payload = _factor_payload(factor_key)
    values = payload.get("values") if isinstance(payload, dict) else {}
    item = values.get(symbol) if isinstance(values, dict) else None
    if not isinstance(item, dict):
        return 0.0
    item_date = str(item.get("trade_date") or "")
    if trade_date and item_date and item_date > trade_date:
        return 0.0
    try:
        return float(item.get("value") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _factor_payload(factor_key: str) -> dict[str, Any]:
    cached = _local_get(factor_key)
    if cached is not None:
        return cached
    payload = get_json_cache(_value_cache_key(factor_key))
    if not isinstance(payload, dict):
        raw = _load_setting_value(f"{_VALUE_PREFIX}{factor_key}")
        try:
            payload = json.loads(raw or "{}")
        except (TypeError, ValueError):
            payload = {}
    _local_set(factor_key, payload if isinstance(payload, dict) else {})
    return payload if isinstance(payload, dict) else {}


def _local_get(key: str) -> dict[str, Any] | None:
    with _LOCK:
        cached = _LOCAL_CACHE.get(key)
        if cached and cached[0] > time.monotonic():
            return dict(cached[1])
        _LOCAL_CACHE.pop(key, None)
    return None


def _local_set(key: str, payload: dict[str, Any]) -> None:
    with _LOCK:
        _LOCAL_CACHE[key] = (time.monotonic() + _LOCAL_CACHE_TTL, dict(payload))


def _load_setting_value(key: str) -> str:
    try:
        with SessionLocal() as db:
            row = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
            return str(row.value or "") if row else ""
    except Exception:
        return ""


def _upsert_setting(db: Session, key: str, value: str) -> None:
    row = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
    if row is None:
        db.add(SystemSetting(key=key, value=value))
    else:
        row.value = value


def _value_cache_key(factor_key: str) -> str:
    return f"factor_mining:value:{factor_key}"
