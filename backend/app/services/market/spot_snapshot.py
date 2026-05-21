from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from math import ceil
import threading
import time
from typing import Any

import requests

from app.models.schemas import QuoteSnapshot
from app.services.market.providers.akshare_utils import parse_spot_snapshot_records
from app.services.market.shared import _safe_str
from app.services.market.shared import ak


_EASTMONEY_STOCK_FIELDS = "f12,f13,f14,f2,f3,f4,f5,f6,f15,f16,f17,f18,f8,f10,f124"
_EASTMONEY_STOCK_SCOPE = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
_PAGE_SIZE = 100
_MAX_PAGES = 80
_MAX_WORKERS = 8
_PAGE_RETRIES = 2
_BUSY_WAIT_SECONDS = 3.0
_SNAPSHOT_CACHE_SECONDS = 8.0
_SPOT_EXECUTOR = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="em-spot")
_FETCH_LOCK = threading.Lock()
_CACHE_LOCK = threading.RLock()
_LAST_SNAPSHOT_AT = 0.0
_LAST_SNAPSHOT: dict[str, QuoteSnapshot] = {}
logger = logging.getLogger(__name__)


def fetch_eastmoney_stock_spot_snapshot_map(service: Any) -> dict[str, QuoteSnapshot]:
    """Fetch one live all-A-share quote snapshot from EastMoney clist.

    This is used for market breadth/emotion. It is intentionally a single
    batched market request rather than thousands of symbol requests.
    """

    cached = _fresh_cached_snapshot()
    acquired = _FETCH_LOCK.acquire(timeout=_BUSY_WAIT_SECONDS)
    if not acquired:
        if cached:
            logger.info("EastMoney spot snapshot fetch already running; returning cached snapshot")
            return cached
        logger.warning("EastMoney spot snapshot fetch already running and no fresh cache is available")
        return {}
    try:
        cached = _fresh_cached_snapshot()
        if cached:
            return cached
        try:
            first_payload = _fetch_page_payload(service, 1)
        except Exception as exc:
            logger.warning("EastMoney first spot page failed, falling back to AkShare snapshot: %s", exc)
            return _fetch_akshare_stock_snapshot_map(service)
        data = first_payload.get("data") or {}
        rows = list(data.get("diff") or [])
        total = int(data.get("total") or len(rows) or 0)
        page_count = min(max(ceil(total / _PAGE_SIZE), 1), _MAX_PAGES)
        if page_count > 1:
            rows.extend(_fetch_remaining_pages(service, page_count))
        result = parse_eastmoney_spot_rows(service, rows)
        _store_cached_snapshot(result)
        return result
    finally:
        _FETCH_LOCK.release()


def parse_eastmoney_spot_rows(service: Any, rows: list[dict[str, object]]) -> dict[str, QuoteSnapshot]:
    result: dict[str, QuoteSnapshot] = {}
    for row in rows:
        symbol = _safe_str(row.get("f12")).strip()
        if not symbol:
            continue
        snapshot = service._build_eastmoney_realtime_quote_snapshot(symbol, row)
        if snapshot.last_price > 0:
            result[symbol] = snapshot
    return result


def _fetch_akshare_stock_snapshot_map(service: Any) -> dict[str, QuoteSnapshot]:
    if ak is None:
        return {}
    raw_client = getattr(service, "akshare_raw", None)
    if raw_client is None:
        return {}
    try:
        frame = raw_client.call(ak.stock_zh_a_spot, purpose="spot_snapshot")
    except Exception as exc:
        logger.warning("AkShare stock spot fallback failed: %s", exc)
        return {}
    if frame is None or getattr(frame, "empty", False):
        return {}
    return parse_spot_snapshot_records(
        frame.to_dict("records"),
        instrument_type="stock",
        source="akshare",
        normalize_timestamp=service._normalize_quote_timestamp,
    )


def _fetch_remaining_pages(service: Any, page_count: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    futures = [_SPOT_EXECUTOR.submit(_fetch_page_payload, service, page) for page in range(2, page_count + 1)]
    for future in as_completed(futures):
        try:
            payload = future.result()
            rows.extend(((payload.get("data") or {}).get("diff") or []))
        except Exception as exc:
            logger.warning("EastMoney spot page fetch failed and was skipped: %s", exc)
    return rows


def _fresh_cached_snapshot() -> dict[str, QuoteSnapshot]:
    with _CACHE_LOCK:
        if _LAST_SNAPSHOT and time.monotonic() - _LAST_SNAPSHOT_AT <= _SNAPSHOT_CACHE_SECONDS:
            return dict(_LAST_SNAPSHOT)
    return {}


def _store_cached_snapshot(snapshot: dict[str, QuoteSnapshot]) -> None:
    global _LAST_SNAPSHOT_AT, _LAST_SNAPSHOT
    if not snapshot:
        return
    with _CACHE_LOCK:
        _LAST_SNAPSHOT = dict(snapshot)
        _LAST_SNAPSHOT_AT = time.monotonic()


def _fetch_page_payload(service: Any, page: int) -> dict[str, object]:
    params = {
        "pn": page,
        "pz": _PAGE_SIZE,
        "po": 1,
        "np": 1,
        "fltt": 2,
        "invt": 2,
        "fid": "f3",
        "fs": _EASTMONEY_STOCK_SCOPE,
        "fields": _EASTMONEY_STOCK_FIELDS,
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
    }
    last_error: Exception | None = None
    for _ in range(_PAGE_RETRIES):
        try:
            session = requests.Session()
            session.trust_env = False
            response = session.get(
                service.stock_list_endpoint,
                params=params,
                headers=dict(getattr(service.session, "headers", {}) or {}),
                timeout=max(float(service.settings.market_batch_timeout_seconds or 3), 3.0),
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("rc") not in (0, None):
                raise RuntimeError(payload.get("rt") or "EastMoney stock spot snapshot failed")
            return payload
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"EastMoney stock spot page {page} failed: {last_error}")
