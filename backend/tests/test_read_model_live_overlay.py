from __future__ import annotations

import time
from types import SimpleNamespace

from app.models.schema_defs.common import QuoteSnapshot
from app.models.schema_defs.screener_parts.priority import (
    LowBuyPriorityBoardItemOut,
    LowBuyPriorityBoardResponse,
    LowBuyPriorityFamilySectionOut,
)
from app.models.schema_defs.strategy_tracking import StrategyTrackingItemOut, StrategyTrackingListResponse
from app.services.performance.read_model_metrics import read_model_metrics_snapshot, reset_read_model_metrics
from app.services.read_models import live_quote_overlay
from app.services.read_models.live_quote_overlay import apply_priority_board_live_overlay, apply_strategy_tracking_live_overlay


def test_priority_board_live_overlay_updates_quote_fields_without_resorting(monkeypatch) -> None:
    reset_read_model_metrics()
    response = LowBuyPriorityBoardResponse(
        as_of_date="2026-06-03",
        latest_trade_date="2026-06-03",
        updated_at="2026-06-03 10:00:00",
        items=[
            _priority_item("000001", 91.0),
            _priority_item("000002", 88.0),
        ],
    )

    requested: list[list[str]] = []

    def fake_batch(symbols: list[str]):
        requested.append(symbols)
        return {"000001": _quote("000001", 12.3, 1.2)}

    monkeypatch.setattr(live_quote_overlay, "read_local_quote_snapshots", fake_batch)

    overlaid = apply_priority_board_live_overlay(response)
    snapshot = read_model_metrics_snapshot()

    assert [item.symbol for item in overlaid.items] == ["000001", "000002"]
    assert overlaid.items[0].latest_price == 12.3
    assert overlaid.items[0].change_pct == 1.2
    assert overlaid.items[0].priority_score == 91.0
    assert overlaid.items[1].latest_price == 10.0
    assert requested == [["000001", "000002"]]
    assert snapshot["live_overlay_hits"]["local_quote_cache"] == 1
    assert snapshot["live_overlay_misses"]["local_quote_cache"] == 1


def test_priority_board_live_overlay_marks_degraded_when_quote_cache_misses(monkeypatch) -> None:
    live_quote_overlay.clear_priority_board_overlay_cache()
    response = LowBuyPriorityBoardResponse(
        as_of_date="2026-06-03",
        latest_trade_date="2026-06-03",
        updated_at="2026-06-03 10:00:00",
        items=[
            _priority_item("000001", 91.0),
            _priority_item("000002", 88.0),
        ],
    )
    monkeypatch.setattr(live_quote_overlay, "read_local_quote_snapshots", lambda symbols: {})

    overlaid = apply_priority_board_live_overlay(response)

    assert [item.latest_price for item in overlaid.items] == [10.0, 10.0]
    assert overlaid.stale is False
    assert "live_overlay_degraded" in overlaid.data_quality_tags
    assert "实时行情降级" in overlaid.data_quality_text
    assert "实时行情降级" in overlaid.stale_reason


def test_priority_board_live_overlay_includes_family_section_symbols(monkeypatch) -> None:
    response = LowBuyPriorityBoardResponse(
        as_of_date="2026-06-03",
        latest_trade_date="2026-06-03",
        updated_at="2026-06-03 10:00:00",
        items=[_priority_item("000001", 91.0)],
        family_sections=[
            LowBuyPriorityFamilySectionOut(
                family_key="first_board",
                family_text="首板",
                items=[_priority_item("000003", 80.0)],
            )
        ],
    )
    monkeypatch.setattr(
        live_quote_overlay,
        "read_local_quote_snapshots",
        lambda symbols: {"000003": _quote("000003", 13.0, 3.0)},
    )

    overlaid = apply_priority_board_live_overlay(response)

    assert overlaid.items[0].latest_price == 10.0
    assert overlaid.family_sections[0].items[0].latest_price == 13.0


def test_priority_board_overlay_cache_returns_same_payload_as_uncached(monkeypatch) -> None:
    live_quote_overlay.clear_priority_board_overlay_cache()
    response = LowBuyPriorityBoardResponse(
        as_of_date="2026-06-03",
        latest_trade_date="2026-06-03",
        updated_at="2026-06-03 10:00:00",
        items=[_priority_item("000001", 91.0)],
    )
    calls: list[list[str]] = []
    monkeypatch.setattr(
        live_quote_overlay,
        "local_quote_cache_marker",
        lambda: {"version": "v1", "as_of": "2026-06-03 10:30:00"},
    )
    monkeypatch.setattr(
        live_quote_overlay,
        "read_local_quote_snapshots",
        lambda symbols: calls.append(symbols) or {"000001": _quote("000001", 12.3, 1.2)},
    )

    first = apply_priority_board_live_overlay(response)
    second = apply_priority_board_live_overlay(response)

    assert second.model_dump() == first.model_dump()
    assert calls == [["000001"]]


def test_priority_board_overlay_cache_caches_degraded_payload(monkeypatch) -> None:
    live_quote_overlay.clear_priority_board_overlay_cache()
    response = LowBuyPriorityBoardResponse(
        as_of_date="2026-06-03",
        latest_trade_date="2026-06-03",
        updated_at="2026-06-03 10:00:00",
        items=[_priority_item("000001", 91.0)],
    )
    calls: list[list[str]] = []
    monkeypatch.setattr(
        live_quote_overlay,
        "local_quote_cache_marker",
        lambda: {"version": "v1", "as_of": "2026-06-03 10:30:00"},
    )
    monkeypatch.setattr(
        live_quote_overlay,
        "read_local_quote_snapshots",
        lambda symbols: calls.append(symbols) or {},
    )

    first = apply_priority_board_live_overlay(response)
    second = apply_priority_board_live_overlay(response)

    assert first.model_dump() == second.model_dump()
    assert "live_overlay_degraded" in second.data_quality_tags
    assert calls == [["000001"]]


def test_priority_board_overlay_cache_invalidates_on_ranking_field_change(monkeypatch) -> None:
    live_quote_overlay.clear_priority_board_overlay_cache()
    calls: list[list[str]] = []
    quotes = [
        {"000001": _quote("000001", 12.3, 1.2)},
        {"000001": _quote("000001", 12.8, 1.8)},
    ]

    monkeypatch.setattr(
        live_quote_overlay,
        "local_quote_cache_marker",
        lambda: {"version": "v1", "as_of": "2026-06-03 10:30:00"},
    )
    monkeypatch.setattr(
        live_quote_overlay,
        "read_local_quote_snapshots",
        lambda symbols: calls.append(symbols) or quotes[min(len(calls) - 1, len(quotes) - 1)],
    )

    first = apply_priority_board_live_overlay(
        LowBuyPriorityBoardResponse(
            as_of_date="2026-06-03",
            latest_trade_date="2026-06-03",
            updated_at="2026-06-03 10:00:00",
            items=[_priority_item("000001", 91.0)],
        )
    )
    second = apply_priority_board_live_overlay(
        LowBuyPriorityBoardResponse(
            as_of_date="2026-06-03",
            latest_trade_date="2026-06-03",
            updated_at="2026-06-03 10:00:00",
            items=[_priority_item("000001", 92.0)],
        )
    )

    assert first.items[0].latest_price == 12.3
    assert second.items[0].priority_score == 92.0
    assert second.items[0].latest_price == 12.8
    assert calls == [["000001"], ["000001"]]


def test_priority_board_live_overlay_timeout_returns_original_payload(monkeypatch) -> None:
    live_quote_overlay.clear_priority_board_overlay_cache()
    response = LowBuyPriorityBoardResponse(
        as_of_date="2026-06-03",
        latest_trade_date="2026-06-03",
        updated_at="2026-06-03 10:00:00",
        items=[_priority_item("000001", 91.0)],
    )
    monkeypatch.setattr(
        live_quote_overlay,
        "get_settings",
        lambda: SimpleNamespace(
            read_model_live_overlay_enabled=True,
            priority_board_overlay_cache_enabled=False,
            priority_board_live_overlay_timeout_ms=1,
        ),
    )

    def slow_batch(symbols: list[str]):  # noqa: ARG001
        time.sleep(0.05)
        return {"000001": _quote("000001", 12.3, 1.2)}

    monkeypatch.setattr(live_quote_overlay, "read_local_quote_snapshots", slow_batch)

    started = time.perf_counter()
    overlaid = apply_priority_board_live_overlay(response)

    assert (time.perf_counter() - started) < 0.03
    assert overlaid.items[0].latest_price == response.items[0].latest_price
    assert "live_overlay_degraded" in overlaid.data_quality_tags


def test_strategy_tracking_overlay_preserves_current_return_pct(monkeypatch) -> None:
    reset_read_model_metrics()
    response = StrategyTrackingListResponse(
        items=[
            StrategyTrackingItemOut(
                id="a",
                symbol="000001",
                strategy_key="first_board",
                first_signal_price=10.0,
                current_price=10.5,
                current_return_pct=5.0,
            )
        ],
        total=1,
    )
    monkeypatch.setattr(live_quote_overlay, "read_local_quote_snapshots", lambda symbols: {"000001": _quote("000001", 12.0, 2.0)})

    overlaid = apply_strategy_tracking_live_overlay(response)

    assert overlaid.items[0].current_price == 12.0
    assert overlaid.items[0].current_return_pct == 5.0
    assert overlaid.items[0].strategy_key == "first_board"


def _priority_item(symbol: str, score: float) -> LowBuyPriorityBoardItemOut:
    return LowBuyPriorityBoardItemOut(
        symbol=symbol,
        name=f"测试{symbol}",
        strategy_key="first_board",
        strategy_title="首板回调",
        latest_price=10.0,
        change_pct=0.0,
        quote_timestamp="2026-06-03 09:30:00",
        priority_score=score,
        entry_zone_low=9.5,
        entry_zone_high=10.5,
        stop_loss=9.0,
    )


def _quote(symbol: str, price: float, change_pct: float) -> QuoteSnapshot:
    return QuoteSnapshot(
        symbol=symbol,
        name=f"测试{symbol}",
        market="SZ",
        instrument_type="stock",
        last_price=price,
        change_pct=change_pct,
        change_amount=0.1,
        open_price=price - 0.1,
        high_price=price + 0.2,
        low_price=price - 0.2,
        prev_close=price - 0.1,
        volume=1000,
        amount=100000,
        timestamp="2026-06-03 10:30:00",
        data_quality="fresh",
    )
