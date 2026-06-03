from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.models.schema_defs.common import QuoteSnapshot
from app.models.schema_defs.screener_parts.priority import (
    LowBuyPriorityBoardItemOut,
    LowBuyPriorityBoardResponse,
)
from app.models.schema_defs.strategy_tracking import StrategyTrackingItemOut, StrategyTrackingListResponse
from app.models.schema_defs.bff import MonitorWorkspaceBffResponse
from app.services.market.local_quote_cache import read_local_quote_snapshots
from app.services.performance.read_model_metrics import record_live_overlay_hit, record_live_overlay_miss

_SOURCE = "local_quote_cache"


def apply_priority_board_live_overlay(response: LowBuyPriorityBoardResponse) -> LowBuyPriorityBoardResponse:
    if not get_settings().read_model_live_overlay_enabled:
        return response
    quote_map = _quote_map(_priority_board_symbols(response))
    items = [_overlay_priority_item(item, quote_map.get(item.symbol)) for item in response.items]
    sections = [
        section.model_copy(update={"items": [_overlay_priority_item(item, quote_map.get(item.symbol)) for item in section.items]})
        for section in response.family_sections
    ]
    return response.model_copy(update={"items": items, "family_sections": sections})


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
