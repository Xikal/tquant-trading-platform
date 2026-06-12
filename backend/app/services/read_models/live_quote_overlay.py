from __future__ import annotations

import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any

from app.core.config import get_settings
from app.models.schema_defs.common import QuoteSnapshot
from app.models.schema_defs.screener_parts.priority import (
    LowBuyPriorityBoardItemOut,
    LowBuyPriorityBoardResponse,
)
from app.models.schema_defs.strategy_tracking import StrategyTrackingItemOut, StrategyTrackingListResponse
from app.models.schema_defs.bff import MonitorWorkspaceBffResponse
from app.services.market.local_quote_cache import local_quote_cache_marker, read_local_quote_snapshots
from app.services.performance.read_model_metrics import record_live_overlay_hit, record_live_overlay_miss

_SOURCE = "local_quote_cache"
_CACHE_LOCK = threading.RLock()
_OVERLAY_CACHE: dict[str, tuple[float, LowBuyPriorityBoardResponse]] = {}
_QUOTE_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="live-quote-overlay")


def apply_priority_board_live_overlay(response: LowBuyPriorityBoardResponse) -> LowBuyPriorityBoardResponse:
    settings = get_settings()
    if not settings.read_model_live_overlay_enabled:
        return response
    marker = local_quote_cache_marker()
    if getattr(settings, "priority_board_overlay_cache_enabled", True):
        cache_key = _priority_overlay_cache_key(response, marker)
        cached = _get_overlay_cache(cache_key)
        if cached is not None:
            return cached
    symbols = _priority_board_symbols(response)
    quote_map = _quote_map_with_budget(
        symbols,
        timeout_ms=getattr(settings, "priority_board_live_overlay_timeout_ms", 80),
    )
    if not quote_map:
        result = _mark_priority_overlay_degraded(response, symbols=symbols, quote_map={})
        if getattr(settings, "priority_board_overlay_cache_enabled", True):
            _set_overlay_cache(cache_key, result, getattr(settings, "priority_board_overlay_cache_ttl_seconds", 2))
        return result
    items = [_overlay_priority_item(item, quote_map.get(item.symbol)) for item in response.items]
    sections = [
        section.model_copy(update={"items": [_overlay_priority_item(item, quote_map.get(item.symbol)) for item in section.items]})
        for section in response.family_sections
    ]
    result = response.model_copy(update={"items": items, "family_sections": sections})
    if _missing_priority_quote_count(symbols, quote_map) > 0:
        result = _mark_priority_overlay_degraded(result, symbols=symbols, quote_map=quote_map)
    if getattr(settings, "priority_board_overlay_cache_enabled", True):
        _set_overlay_cache(cache_key, result, getattr(settings, "priority_board_overlay_cache_ttl_seconds", 2))
    return result


def apply_strategy_tracking_live_overlay(response: StrategyTrackingListResponse) -> StrategyTrackingListResponse:
    if not get_settings().read_model_live_overlay_enabled:
        return response
    quote_map = _quote_map([item.symbol for item in response.items])
    items = [_overlay_tracking_item(item, quote_map.get(item.symbol)) for item in response.items]
    return response.model_copy(update={"items": items})


def apply_monitor_workspace_live_overlay(response: MonitorWorkspaceBffResponse) -> MonitorWorkspaceBffResponse:
    if not get_settings().read_model_live_overlay_enabled:
        return response
    if response.monitor_snapshot is None:
        return response
    board = response.monitor_snapshot.priority_board
    if not isinstance(board, dict):
        return response
    quote_map = _quote_map(_priority_board_dict_symbols(board))
    updated_board = _overlay_priority_board_dict(board, quote_map)
    monitor_snapshot = response.monitor_snapshot.model_copy(update={"priority_board": updated_board})
    return response.model_copy(update={"monitor_snapshot": monitor_snapshot})


def _overlay_priority_board_dict(board: dict[str, Any], quote_map: dict[str, QuoteSnapshot]) -> dict[str, Any]:
    updated = dict(board)
    updated["items"] = [_overlay_priority_dict(item, quote_map) for item in board.get("items", [])]
    sections: list[dict[str, Any]] = []
    for section in board.get("family_sections", []):
        if not isinstance(section, dict):
            sections.append(section)
            continue
        section_copy = dict(section)
        section_copy["items"] = [_overlay_priority_dict(item, quote_map) for item in section.get("items", [])]
        sections.append(section_copy)
    updated["family_sections"] = sections
    return updated


def _overlay_priority_dict(item: Any, quote_map: dict[str, QuoteSnapshot]) -> Any:
    if not isinstance(item, dict):
        return item
    quote = quote_map.get(str(item.get("symbol") or ""))
    if quote is None:
        return item
    return {
        **item,
        "latest_price": quote.last_price,
        "change_pct": quote.change_pct,
        "quote_timestamp": quote.timestamp,
        "data_quality": quote.data_quality,
    }


def _overlay_priority_item(item: LowBuyPriorityBoardItemOut, quote: QuoteSnapshot | None) -> LowBuyPriorityBoardItemOut:
    if quote is None:
        return item
    return item.model_copy(
        update={
            "latest_price": quote.last_price,
            "change_pct": quote.change_pct,
            "quote_timestamp": quote.timestamp,
            "data_quality": quote.data_quality,
        }
    )


def _overlay_tracking_item(item: StrategyTrackingItemOut, quote: QuoteSnapshot | None) -> StrategyTrackingItemOut:
    if quote is None:
        return item
    return item.model_copy(
        update={
            "current_price": quote.last_price,
            "market_data_updated_at": quote.timestamp,
            "data_quality": quote.data_quality,
        }
    )


def _priority_board_symbols(response: LowBuyPriorityBoardResponse) -> list[str]:
    symbols = [item.symbol for item in response.items]
    for section in response.family_sections:
        symbols.extend(item.symbol for item in section.items)
    return symbols


def _priority_board_dict_symbols(board: dict[str, Any]) -> list[str]:
    symbols = [str(item.get("symbol") or "") for item in board.get("items", []) if isinstance(item, dict)]
    for section in board.get("family_sections", []):
        if not isinstance(section, dict):
            continue
        symbols.extend(str(item.get("symbol") or "") for item in section.get("items", []) if isinstance(item, dict))
    return symbols


def _quote_map(symbols: list[str]) -> dict[str, QuoteSnapshot]:
    requested: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        clean = str(symbol or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        requested.append(clean)
    quotes = read_local_quote_snapshots(requested)
    for symbol in requested:
        if symbol in quotes:
            record_live_overlay_hit(_SOURCE)
        else:
            record_live_overlay_miss(_SOURCE)
    return quotes


def _mark_priority_overlay_degraded(
    response: LowBuyPriorityBoardResponse,
    *,
    symbols: list[str],
    quote_map: dict[str, QuoteSnapshot],
) -> LowBuyPriorityBoardResponse:
    requested_count = len(_unique_symbols(symbols))
    missing_count = _missing_priority_quote_count(symbols, quote_map)
    if requested_count <= 0 or missing_count <= 0:
        return response
    tag = "live_overlay_degraded" if missing_count == requested_count else "live_overlay_partial"
    text = "实时行情降级，当前展示榜单快照价格。" if tag == "live_overlay_degraded" else "实时行情部分降级，缺失股票展示榜单快照价格。"
    return response.model_copy(
        update={
            "data_quality": _overlay_data_quality(response.data_quality, tag),
            "data_quality_text": _append_quality_text(response.data_quality_text, text),
            "data_quality_tags": _unique_tags([*(response.data_quality_tags or []), tag]),
            "stale_reason": _append_quality_text(response.stale_reason, text),
        }
    )


def _missing_priority_quote_count(symbols: list[str], quote_map: dict[str, QuoteSnapshot]) -> int:
    requested = _unique_symbols(symbols)
    return sum(1 for symbol in requested if symbol not in quote_map)


def _unique_symbols(symbols: list[str]) -> list[str]:
    requested: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        clean = str(symbol or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        requested.append(clean)
    return requested


def _unique_tags(tags: list[str]) -> list[str]:
    return list(dict.fromkeys(str(tag) for tag in tags if str(tag)))


def _append_quality_text(current: str, text: str) -> str:
    if not current:
        return text
    if text in current:
        return current
    return f"{current}；{text}"


def _overlay_data_quality(current: str, tag: str) -> str:
    if current in {"unavailable", "limited", "stale", "degraded"}:
        return current
    return "degraded" if tag == "live_overlay_degraded" else "partial"


def _quote_map_with_budget(symbols: list[str], *, timeout_ms: int | float | None) -> dict[str, QuoteSnapshot]:
    budget = float(timeout_ms or 0)
    if budget <= 0:
        return {}
    future = _QUOTE_EXECUTOR.submit(_quote_map, list(symbols))
    try:
        return future.result(timeout=budget / 1000.0)
    except TimeoutError:
        future.cancel()
        return {}
    except Exception:
        return {}


def _priority_overlay_cache_key(response: LowBuyPriorityBoardResponse, marker: dict[str, Any]) -> str:
    parts = [
        str(marker.get("version") or ""),
        str(marker.get("as_of") or ""),
        str(response.as_of_date or ""),
        str(response.latest_trade_date or ""),
        str(response.latest_available_trade_date or ""),
        str(response.updated_at or ""),
        str(response.total_candidates),
        str(response.data_quality or ""),
        ",".join(str(tag) for tag in (response.data_quality_tags or [])),
        str(response.snapshot_warning or ""),
        str(getattr(response, "strategy_variant", "") or ""),
    ]
    parts.extend(_priority_item_fingerprint(item) for item in response.items)
    for section in response.family_sections:
        parts.append(str(section.family_key or ""))
        parts.extend(_priority_item_fingerprint(item) for item in section.items)
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _priority_item_fingerprint(item: LowBuyPriorityBoardItemOut) -> str:
    return hashlib.sha256(
        item.model_dump_json(
            exclude={
                "latest_price",
                "change_pct",
                "change_amount",
                "quote_timestamp",
                "data_quality",
            }
        ).encode("utf-8")
    ).hexdigest()


def _get_overlay_cache(cache_key: str) -> LowBuyPriorityBoardResponse | None:
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _OVERLAY_CACHE.get(cache_key)
        if cached is None:
            return None
        expires_at, payload = cached
        if expires_at <= now:
            _OVERLAY_CACHE.pop(cache_key, None)
            return None
        return payload.model_copy(deep=True)


def _set_overlay_cache(cache_key: str, payload: LowBuyPriorityBoardResponse, ttl_seconds: int | float) -> None:
    with _CACHE_LOCK:
        _OVERLAY_CACHE[cache_key] = (
            time.monotonic() + max(float(ttl_seconds or 2), 0.1),
            payload.model_copy(deep=True),
        )


def clear_priority_board_overlay_cache() -> None:
    with _CACHE_LOCK:
        _OVERLAY_CACHE.clear()
