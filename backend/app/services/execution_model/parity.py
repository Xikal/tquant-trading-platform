from __future__ import annotations

from decimal import Decimal
from typing import Any

from scripts.low_buy_market_backtest_reporting import TradeOutcome, portfolio_backtest_metrics

from app.services.execution_model.events import (
    ExecutionFill,
    ExecutionOrder,
    ExecutionPosition,
    ExecutionSignal,
    ExitEvent,
)
from app.services.execution_model.portfolio_preview import run_max5_max10_preview
from app.services.execution_model.rules import available_quantity_for_date, lot_sized_quantity, position_return_pct


PARITY_VERSION = "execution-model-parity-v1"
PARITY_FIELDS = ("profit_factor", "avg_trade_return_pct", "portfolio_return_pct", "max_drawdown_pct", "trade_count")


def build_backtest_execution_model_preview(outcomes: list[TradeOutcome]) -> dict[str, Any]:
    """Build a display-only execution-model preview for existing backtest outcomes."""

    events = _events_from_outcomes(outcomes, source="backtest")
    preview = run_max5_max10_preview(outcomes)
    canonical_max5 = portfolio_backtest_metrics(outcomes, max_positions=5)
    canonical_max10 = portfolio_backtest_metrics(outcomes, max_positions=10)
    return _preview_payload(
        source="backtest",
        events=events,
        preview=preview,
        canonical={"max_5": canonical_max5, "max_10": canonical_max10},
    )


def build_paper_execution_model_preview(outcomes: list[TradeOutcome]) -> dict[str, Any]:
    """Build a display-only execution-model preview for paper outcome snapshots."""

    events = _events_from_outcomes(outcomes, source="paper")
    preview = run_max5_max10_preview(outcomes)
    canonical_max5 = portfolio_backtest_metrics(outcomes, max_positions=5)
    canonical_max10 = portfolio_backtest_metrics(outcomes, max_positions=10)
    return _preview_payload(
        source="paper",
        events=events,
        preview=preview,
        canonical={"max_5": canonical_max5, "max_10": canonical_max10},
    )


def _preview_payload(
    *,
    source: str,
    events: list[Any],
    preview: dict[str, Any],
    canonical: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "parallel_preview",
        "source": source,
        "execution_model_version": PARITY_VERSION,
        "event_counts": _event_counts(events),
        "position_summary": _position_summary(events),
        "exit_reason_counts": _exit_reason_counts(events),
        "max_5": preview.get("max_5") or {},
        "max_10": preview.get("max_10") or {},
        "parity": {
            "max_5": _parity_fields(preview.get("max_5") or {}, canonical["max_5"]),
            "max_10": _parity_fields(preview.get("max_10") or {}, canonical["max_10"]),
        },
        "final_fact_source": "portfolio_backtest_metrics",
        "replacement_enabled": False,
        "notes": [
            "execution_model preview runs in parallel and does not replace backtest or paper facts.",
            "portfolio_backtest_metrics remains the final max5/max10 fact source.",
        ],
    }


def _events_from_outcomes(outcomes: list[TradeOutcome], *, source: str) -> list[Any]:
    events: list[Any] = []
    for outcome in outcomes:
        signal_date = str(outcome.signal_date or outcome.entry_trade_date or "")
        entry_date = str(outcome.entry_trade_date or signal_date)
        exit_date = str(outcome.exit_trade_date or entry_date)
        quantity = lot_sized_quantity(100)
        entry_price = Decimal(str(outcome.entry_price or 0))
        exit_price = _exit_price(entry_price, outcome.net_return_pct)
        events.append(
            ExecutionSignal(
                symbol=outcome.symbol,
                trade_date=signal_date,
                strategy_key=outcome.strategy_key,
                source=source,
                signal_state=outcome.buy_signal_state,
                score=outcome.production_score,
            )
        )
        if str(outcome.execution_status or "") != "filled":
            continue
        events.append(
            ExecutionOrder(
                symbol=outcome.symbol,
                trade_date=entry_date,
                strategy_key=outcome.strategy_key,
                source=source,
                side="buy",
                quantity=quantity,
                requested_price=entry_price,
            )
        )
        events.append(
            ExecutionFill(
                symbol=outcome.symbol,
                trade_date=entry_date,
                strategy_key=outcome.strategy_key,
                source=source,
                side="buy",
                quantity=quantity,
                fill_price=entry_price,
            )
        )
        events.append(
            ExecutionPosition(
                symbol=outcome.symbol,
                trade_date=entry_date,
                strategy_key=outcome.strategy_key,
                source=source,
                quantity=quantity,
                available_quantity=available_quantity_for_date(
                    [(quantity, exit_date)],
                    trade_date=entry_date,
                    symbol=outcome.symbol,
                ),
                cost_basis=entry_price,
                market_price=exit_price,
            )
        )
        events.append(
            ExitEvent(
                symbol=outcome.symbol,
                trade_date=exit_date,
                strategy_key=outcome.strategy_key,
                source=source,
                quantity=quantity,
                exit_price=exit_price,
                exit_reason=str(outcome.execution_exit_reason or "unknown"),
                return_pct=position_return_pct(entry_price=entry_price, exit_price=exit_price),
            )
        )
    return events


def _event_counts(events: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        counts[event.kind] = counts.get(event.kind, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _position_summary(events: list[Any]) -> dict[str, Any]:
    positions = [event for event in events if getattr(event, "kind", "") == "position"]
    return {
        "position_count": len(positions),
        "total_quantity": sum(int(position.quantity or 0) for position in positions),
        "available_quantity": sum(int(position.available_quantity or 0) for position in positions),
    }


def _exit_reason_counts(events: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        if getattr(event, "kind", "") != "exit":
            continue
        reason = str(getattr(event, "exit_reason", "") or "unknown")
        counts[reason] = counts.get(reason, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _parity_fields(preview: dict[str, Any], canonical: dict[str, Any]) -> dict[str, bool]:
    return {field: preview.get(field) == canonical.get(field) for field in PARITY_FIELDS}


def _exit_price(entry_price: Decimal, return_pct: float) -> Decimal:
    return entry_price * (Decimal("1") + Decimal(str(return_pct or 0)) / Decimal("100"))
