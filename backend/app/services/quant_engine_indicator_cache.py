from __future__ import annotations

import time
from collections import OrderedDict
from threading import Lock
from typing import Callable

from app.models.schemas import KlineBar, QuoteSnapshot
from app.services.quant_engine_models import IndicatorSnapshot


_MAX_ENTRIES = 512
_TTL_SECONDS = 20.0
_LOCK = Lock()
_CACHE: OrderedDict[str, tuple[float, IndicatorSnapshot]] = OrderedDict()


def indicator_cache_key(quote: QuoteSnapshot, bars: list[KlineBar]) -> str:
    if not bars:
        return f"empty:{quote.symbol}:{quote.timestamp}:{quote.last_price}"
    first = bars[0]
    last = bars[-1]
    return "|".join(
        [
            str(quote.symbol),
            str(len(bars)),
            str(first.timestamp),
            str(last.timestamp),
            f"{float(last.close):.4f}",
            f"{float(last.volume):.4f}",
            f"{float(quote.last_price or 0):.4f}",
            f"{float(quote.prev_close or 0):.4f}",
            f"{float(quote.volume_ratio or 0):.4f}",
            str(quote.timestamp or ""),
        ]
    )


def get_or_compute_indicator_snapshot(key: str, factory: Callable[[], IndicatorSnapshot]) -> IndicatorSnapshot:
    now = time.monotonic()
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and now - cached[0] <= _TTL_SECONDS:
            _CACHE.move_to_end(key)
            return cached[1]
    value = factory()
    with _LOCK:
        _CACHE[key] = (now, value)
        _CACHE.move_to_end(key)
        while len(_CACHE) > _MAX_ENTRIES:
            _CACHE.popitem(last=False)
    return value


def clear_indicator_cache() -> None:
    with _LOCK:
        _CACHE.clear()
