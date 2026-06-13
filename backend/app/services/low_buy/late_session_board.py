from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any

from app.models.schema_defs.late_session_board import (
    LateSessionBoardItemOut,
    LateSessionBoardResponse,
    LateSessionBoardStatus,
    LateSessionDegradationReason,
    LateSessionItemState,
    LateSessionSnapshotSlot,
)
from app.models.schemas import LowBuyPriorityBoardResponse
from app.services.low_buy.intraday_confirmation import build_intraday_confirmation
from app.services.low_buy.late_session_policy import (
    classify_late_session_strategy,
    late_session_score_cap,
    late_session_strategy_allowed_for_formal,
)


def build_late_session_board(
    *,
    candidates: list[dict[str, object]],
    minute_bars_by_symbol: dict[str, list[object]],
    quotes_by_symbol: dict[str, dict[str, object]] | None = None,
    market_state: str | None = None,
    trade_date: str = "",
    snapshot_slot: LateSessionSnapshotSlot = LateSessionSnapshotSlot.LATEST,
    source_priority_board_epoch: str = "",
    limit: int = 12,
    refresh_mode: str = "cache",
) -> LateSessionBoardResponse:
    quotes = quotes_by_symbol or {}
    clean_slot = _snapshot_slot(snapshot_slot)
    clean_limit = max(1, min(int(limit or 12), 30))
    board_tags: list[str] = []
    items: list[LateSessionBoardItemOut] = []
    for order, candidate in enumerate(candidates[:30]):
        item = _build_item(
            candidate=dict(candidate),
            minute_bars=minute_bars_by_symbol.get(_text(candidate.get("symbol"))),
            quote=quotes.get(_text(candidate.get("symbol"))),
            market_state=str(market_state or "").strip().lower(),
            snapshot_slot=clean_slot,
            order=order,
        )
        board_tags.extend(item.reject_reasons)
        board_tags.extend(item.risk_tags)
        items.append(item)

    data_quality_tags = sorted(set(board_tags))
    if not items:
        status = LateSessionBoardStatus.UNAVAILABLE
        degradation = LateSessionDegradationReason.BLOCKED_BY_MATERIALIZATION.value
    elif any(item.late_session_state == LateSessionItemState.LATE_UNAVAILABLE for item in items):
        status = LateSessionBoardStatus.PARTIAL_DATA
        degradation = _first_degradation(data_quality_tags)
    elif "market_context_missing" in data_quality_tags:
        status = LateSessionBoardStatus.PARTIAL_DATA
        degradation = LateSessionDegradationReason.MARKET_CONTEXT_MISSING.value
    else:
        status = LateSessionBoardStatus.OK
        degradation = ""

    return LateSessionBoardResponse(
        trade_date=trade_date,
        snapshot_slot=clean_slot,
        generated_at=datetime.now(),
        source_priority_board_epoch=source_priority_board_epoch,
        status=status,
        items=items[:clean_limit],
        data_quality=status.value,
        data_quality_tags=data_quality_tags,
        degradation_reason=degradation,
        refresh_mode=refresh_mode,
        source={"candidate_count": len(candidates), "source": "priority_board"},
    )


def build_late_session_board_from_priority_response(
    priority_board: LowBuyPriorityBoardResponse,
    *,
    quotes_by_symbol: dict[str, dict[str, object]] | None = None,
    minute_bars_by_symbol: dict[str, list[object]] | None = None,
    slot: LateSessionSnapshotSlot | str = LateSessionSnapshotSlot.LATEST,
    limit: int = 12,
    refresh_mode: str = "cache",
) -> LateSessionBoardResponse:
    candidates = [_candidate_from_priority_item(item) for item in priority_board.items]
    fallback_quotes = {
        str(item.symbol): {
            "latest_price": item.latest_price,
            "timestamp": item.quote_timestamp,
        }
        for item in priority_board.items
        if getattr(item, "latest_price", None) is not None
    }
    fallback_quotes.update(quotes_by_symbol or {})
    return build_late_session_board(
        candidates=candidates,
        minute_bars_by_symbol=minute_bars_by_symbol or {},
        quotes_by_symbol=fallback_quotes,
        market_state=_market_state_from_priority_board(priority_board),
        trade_date=str(priority_board.latest_trade_date or priority_board.latest_available_trade_date or ""),
        snapshot_slot=_snapshot_slot(slot),
        source_priority_board_epoch=_priority_epoch(priority_board),
        limit=limit,
        refresh_mode=refresh_mode,
    )


def _build_item(
    *,
    candidate: dict[str, object],
    minute_bars: list[object] | None,
    quote: dict[str, object] | None,
    market_state: str,
    snapshot_slot: LateSessionSnapshotSlot,
    order: int,
) -> LateSessionBoardItemOut:
    symbol = _text(candidate.get("symbol"))
    strategy_key = _text(candidate.get("strategy_key") or candidate.get("strategy"))
    strategy_layer = classify_late_session_strategy(strategy_key)
    risk_tags: list[str] = []
    reject_reasons: list[str] = []

    if not late_session_strategy_allowed_for_formal(strategy_key):
        risk_tags.append("research_only")
    if not market_state:
        reject_reasons.append(LateSessionDegradationReason.MARKET_CONTEXT_MISSING.value)
    elif market_state == "block":
        reject_reasons.append("market_block")

    if not quote:
        reject_reasons.append(LateSessionDegradationReason.QUOTE_UNAVAILABLE.value)
    bars = [_bar_object(row) for row in (minute_bars or [])]
    if not bars:
        reject_reasons.append(LateSessionDegradationReason.MINUTE_DATA_MISSING.value)
        return _item(
            candidate=candidate,
            strategy_key=strategy_key,
            strategy_layer=strategy_layer,
            state=LateSessionItemState.LATE_UNAVAILABLE,
            score=0.0,
            reason="分钟线缺失，尾盘确认降级为数据不足。",
            snapshot_slot=snapshot_slot,
            risk_tags=risk_tags,
            reject_reasons=reject_reasons,
            latest_price=_float((quote or {}).get("latest_price")),
            quote_timestamp=_text((quote or {}).get("timestamp")),
            order=order,
        )

    confirmation = build_intraday_confirmation(bars)
    latest_price = _float((quote or {}).get("latest_price")) or _float(getattr(bars[-1], "close", 0.0))
    if not confirmation.usable or confirmation.vwap <= 0:
        reject_reasons.append(LateSessionDegradationReason.VWAP_UNAVAILABLE.value)
        state = LateSessionItemState.LATE_UNAVAILABLE
    elif not late_session_strategy_allowed_for_formal(strategy_key):
        state = LateSessionItemState.LATE_WATCH
    elif market_state in {"", "block"}:
        state = LateSessionItemState.LATE_WATCH
    elif not quote:
        state = LateSessionItemState.LATE_WATCH
    elif confirmation.late_confirmed:
        state = LateSessionItemState.LATE_CONFIRMED
    elif confirmation.above_vwap:
        state = LateSessionItemState.LATE_WATCH
        reject_reasons.append("late_confirmation_insufficient")
    else:
        state = LateSessionItemState.LATE_REJECTED
        reject_reasons.append("below_vwap")

    raw_score = _float(candidate.get("production_score")) or _float(candidate.get("priority_score"))
    score = late_session_score_cap(strategy_key, raw_score if state == LateSessionItemState.LATE_CONFIRMED else raw_score * 0.72)
    return _item(
        candidate=candidate,
        strategy_key=strategy_key,
        strategy_layer=strategy_layer,
        state=state,
        score=score,
        reason=_reason(state, confirmation.reason),
        snapshot_slot=snapshot_slot,
        risk_tags=risk_tags,
        reject_reasons=reject_reasons,
        latest_price=latest_price,
        quote_timestamp=_text((quote or {}).get("timestamp") or (quote or {}).get("quote_timestamp")),
        order=order,
        vwap=confirmation.vwap,
        above_vwap=confirmation.above_vwap,
        late_session_strength=confirmation.late_session_strength,
        low_rising=confirmation.low_rising,
    )


def _candidate_from_priority_item(item: object) -> dict[str, object]:
    if hasattr(item, "model_dump"):
        payload = item.model_dump(mode="json")
        return payload if isinstance(payload, dict) else {}
    return dict(item) if isinstance(item, dict) else {}


def _market_state_from_priority_board(priority_board: LowBuyPriorityBoardResponse) -> str:
    gate = str(getattr(priority_board, "market_gate_decision", "") or "").strip().lower()
    if gate in {"allow", "reduce", "block"}:
        return gate
    raw = str(getattr(priority_board, "market_state", "") or "").strip().lower()
    if raw in {"allow", "reduce", "block"}:
        return raw
    return "allow" if raw else ""


def _priority_epoch(priority_board: LowBuyPriorityBoardResponse) -> str:
    return ":".join(
        item
        for item in (
            str(getattr(priority_board, "latest_trade_date", "") or ""),
            str(getattr(priority_board, "updated_at", "") or ""),
            str(getattr(priority_board, "total_candidates", "") or ""),
        )
        if item
    )


def _item(
    *,
    candidate: dict[str, object],
    strategy_key: str,
    strategy_layer: str,
    state: LateSessionItemState,
    score: float,
    reason: str,
    snapshot_slot: LateSessionSnapshotSlot,
    risk_tags: list[str],
    reject_reasons: list[str],
    latest_price: float | None,
    quote_timestamp: str,
    order: int,
    vwap: float | None = None,
    above_vwap: bool | None = None,
    late_session_strength: bool | None = None,
    low_rising: bool | None = None,
) -> LateSessionBoardItemOut:
    return LateSessionBoardItemOut(
        symbol=_text(candidate.get("symbol")),
        name=_text(candidate.get("name") or candidate.get("stock_name")),
        strategy_key=strategy_key,
        strategy_layer=strategy_layer,
        priority_score=_float(candidate.get("priority_score")),
        production_score=_float(candidate.get("production_score")),
        buy_signal_state=_text(candidate.get("buy_signal_state")),
        late_session_state=state,
        late_session_score=round(score, 4),
        late_session_reason=reason,
        vwap=vwap,
        latest_price=latest_price,
        above_vwap=above_vwap,
        late_session_strength=late_session_strength,
        low_rising=low_rising,
        risk_tags=list(dict.fromkeys(risk_tags)),
        reject_reasons=list(dict.fromkeys(reject_reasons)),
        quote_timestamp=quote_timestamp,
        snapshot_slot=snapshot_slot,
        source={"priority_board_order": order},
    )


def _snapshot_slot(value: LateSessionSnapshotSlot | str) -> LateSessionSnapshotSlot:
    if isinstance(value, LateSessionSnapshotSlot):
        return value
    try:
        return LateSessionSnapshotSlot(str(value or "latest"))
    except ValueError:
        return LateSessionSnapshotSlot.LATEST


def _bar_object(row: object) -> object:
    if isinstance(row, dict):
        return SimpleNamespace(**row)
    return row


def _reason(state: LateSessionItemState, confirmation_reason: str) -> str:
    if state == LateSessionItemState.LATE_CONFIRMED:
        return f"尾盘确认：{confirmation_reason}"
    if state == LateSessionItemState.LATE_WATCH:
        return f"尾盘观察：{confirmation_reason}"
    if state == LateSessionItemState.LATE_REJECTED:
        return f"不满足尾盘确认：{confirmation_reason}"
    return "数据不足：尾盘确认不可用。"


def _first_degradation(tags: list[str]) -> str:
    for reason in (
        LateSessionDegradationReason.MINUTE_DATA_MISSING.value,
        LateSessionDegradationReason.QUOTE_UNAVAILABLE.value,
        LateSessionDegradationReason.VWAP_UNAVAILABLE.value,
        LateSessionDegradationReason.MARKET_CONTEXT_MISSING.value,
    ):
        if reason in tags:
            return reason
    return LateSessionDegradationReason.PARTIAL_DATA.value


def _text(value: object) -> str:
    return str(value or "").strip()


def _float(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
