from __future__ import annotations

import time
from typing import Any

from app.models.schemas import LowBuyPriorityBoardResponse
from app.services.low_buy.late_session_board import build_late_session_board_from_priority_response
from app.services.low_buy.late_session_cache import (
    late_session_cache_key,
    late_session_ttl_seconds,
    store_distributed_late_session_board_snapshot,
    store_late_session_board_snapshot,
)
from app.services.low_buy.late_session_policy import LATE_SESSION_SOURCE_CANDIDATE_LIMIT
from app.services.low_buy_screener import LowBuyScreenerService

low_buy_screener = LowBuyScreenerService()
_TASK_SNAPSHOT_CACHE: dict[str, tuple[float, str]] = {}


def late_session_idempotency_key(trade_date: str, slot: str) -> str:
    clean_date = str(trade_date or "unknown").strip() or "unknown"
    clean_slot = str(slot or "latest").strip() or "latest"
    return f"late_session_recommendation_refresh:{clean_date}:{clean_slot}"


def refresh_late_session_recommendation(db, payload: dict[str, object]) -> dict[str, object]:  # noqa: ANN001
    started_at = time.monotonic()
    slot = str(payload.get("slot") or "latest")
    strategy_variant = str(payload.get("strategy_variant") or "baseline")
    limit = max(1, min(int(payload.get("limit") or 12), 30))
    source_limit = max(limit, min(int(payload.get("source_limit") or LATE_SESSION_SOURCE_CANDIDATE_LIMIT), 30))
    board = low_buy_screener.priority_board(
        db=db,
        limit=source_limit,
        refresh_mode="cache",
        strategy_variant=strategy_variant,
    )
    if not getattr(board, "latest_trade_date", "") or not getattr(board, "items", []):
        return _result(
            ok=False,
            slot=slot,
            trade_date=str(payload.get("trade_date") or getattr(board, "latest_trade_date", "") or ""),
            item_count=0,
            confirmed_count=0,
            degradation_reason="blocked_by_materialization",
            started_at=started_at,
        )

    symbols = [str(item.symbol) for item in board.items[:source_limit]]
    response = build_late_session_board_from_priority_response(
        board,
        quotes_by_symbol=_quote_map_for_symbols(symbols),
        minute_bars_by_symbol=_minute_bars_for_symbols(symbols),
        slot=slot,
        limit=limit,
        refresh_mode="task",
    )
    _store_task_snapshot(response, strategy_variant=strategy_variant)
    confirmed_count = sum(1 for item in response.items if item.late_session_state == "late_confirmed")
    return _result(
        ok=response.status in {"ok", "partial_data"},
        slot=slot,
        trade_date=response.trade_date,
        item_count=len(response.items),
        confirmed_count=confirmed_count,
        degradation_reason=response.degradation_reason,
        started_at=started_at,
    )


def _quote_map_for_symbols(symbols: list[str]) -> dict[str, dict[str, object]]:
    try:
        from app.services.market.local_quote_cache import read_local_quote_snapshots

        snapshots = read_local_quote_snapshots(symbols)
    except Exception:
        snapshots = {}
    return {
        symbol: {
            "latest_price": getattr(snapshot, "last_price", None),
            "timestamp": getattr(snapshot, "timestamp", ""),
        }
        for symbol, snapshot in snapshots.items()
        if snapshot is not None
    }


def _minute_bars_for_symbols(symbols: list[str]) -> dict[str, list[Any]]:
    try:
        from app.services.market_data import MarketDataService

        return MarketDataService().get_intraday_bars_batch(
            symbols=symbols,
            period="1m",
            limit=30,
            max_workers=4,
            allow_slow_fallback=False,
        )
    except Exception:
        return {}


def _store_task_snapshot(response, *, strategy_variant: str) -> None:  # noqa: ANN001
    key = late_session_cache_key(
        trade_date=response.trade_date,
        slot=response.snapshot_slot.value,
        strategy_variant=strategy_variant,
        source_epoch=response.source_priority_board_epoch,
    )
    store_late_session_board_snapshot(
        _TASK_SNAPSHOT_CACHE,
        key,
        response,
        ttl_seconds=late_session_ttl_seconds(response.snapshot_slot.value),
    )
    store_distributed_late_session_board_snapshot(
        key,
        response,
        ttl_seconds=late_session_ttl_seconds(response.snapshot_slot.value),
    )


def _result(
    *,
    ok: bool,
    slot: str,
    trade_date: str,
    item_count: int,
    confirmed_count: int,
    degradation_reason: str,
    started_at: float,
) -> dict[str, object]:
    return {
        "ok": ok,
        "task_type": "late_session_recommendation_refresh",
        "slot": slot,
        "trade_date": trade_date,
        "item_count": item_count,
        "confirmed_count": confirmed_count,
        "degradation_reason": degradation_reason,
        "elapsed_ms": round((time.monotonic() - started_at) * 1000, 3),
        "worker_scope": "runtime-worker",
    }
