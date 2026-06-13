from __future__ import annotations

from types import SimpleNamespace

from app.models.schemas import LowBuyPriorityBoardItemOut, LowBuyPriorityBoardResponse
from app.services.low_buy.late_session_tasks import (
    late_session_idempotency_key,
    refresh_late_session_recommendation,
)
from app.workers import runtime_worker


def _board() -> LowBuyPriorityBoardResponse:
    return LowBuyPriorityBoardResponse(
        as_of_date="2026-06-13",
        latest_trade_date="2026-06-13",
        latest_available_trade_date="2026-06-13",
        updated_at="2026-06-13 14:57:00",
        total_candidates=1,
        market_gate_decision="allow",
        items=[
            LowBuyPriorityBoardItemOut(
                symbol="000001",
                name="平安银行",
                strategy_key="first_board",
                strategy_title="首板回调",
                priority_score=88,
                production_score=82,
                buy_signal_state="watch",
                latest_price=10.16,
                change_pct=0.8,
                quote_timestamp="2026-06-13 14:57:00",
                entry_zone_low=9.8,
                entry_zone_high=10.2,
                stop_loss=9.5,
            )
        ],
    )


def test_runtime_worker_dispatches_late_session_refresh(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_refresh(db, payload):  # noqa: ANN001
        calls.append(payload)
        return {"ok": True, "task_type": "late_session_recommendation_refresh"}

    monkeypatch.setattr("app.services.low_buy.late_session_tasks.refresh_late_session_recommendation", fake_refresh)

    result = runtime_worker._execute_task(
        "late_session_recommendation_refresh",
        {"slot": "final_1457"},
        SimpleNamespace(),
    )

    assert result["ok"] is True
    assert calls == [{"slot": "final_1457"}]
    assert "late_session_recommendation_refresh" in runtime_worker.RUNTIME_WORKER_TASK_TYPES


def test_late_session_task_uses_slot_specific_idempotency_key() -> None:
    assert (
        late_session_idempotency_key("2026-06-13", "final_1457")
        == "late_session_recommendation_refresh:2026-06-13:final_1457"
    )


def test_late_session_task_never_calls_full_market_scan(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "app.services.low_buy.late_session_tasks.low_buy_screener.priority_board",
        lambda **_kwargs: calls.append("priority_board") or _board(),
    )
    monkeypatch.setattr(
        "app.services.low_buy.late_session_tasks.low_buy_screener.screen",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("full scan must not run")),
    )
    monkeypatch.setattr(
        "app.services.low_buy.late_session_tasks._quote_map_for_symbols",
        lambda symbols: {symbol: {"latest_price": 10.16, "timestamp": "2026-06-13 14:57:00"} for symbol in symbols},
    )
    monkeypatch.setattr(
        "app.services.low_buy.late_session_tasks._minute_bars_for_symbols",
        lambda symbols: {symbol: _confirmed_minutes() for symbol in symbols},
    )

    result = refresh_late_session_recommendation(SimpleNamespace(), {"slot": "final_1457", "limit": 12})

    assert result["ok"] is True
    assert result["task_type"] == "late_session_recommendation_refresh"
    assert result["item_count"] == 1
    assert calls == ["priority_board"]


def test_late_session_task_records_degradation_when_source_board_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.low_buy.late_session_tasks.low_buy_screener.priority_board",
        lambda **_kwargs: LowBuyPriorityBoardResponse(
            as_of_date="2026-06-13",
            latest_trade_date="",
            latest_available_trade_date="2026-06-13",
            updated_at="",
            total_candidates=0,
            items=[],
        ),
    )

    result = refresh_late_session_recommendation(SimpleNamespace(), {"slot": "preview_1450", "limit": 12})

    assert result["ok"] is False
    assert result["degradation_reason"] == "blocked_by_materialization"
    assert result["item_count"] == 0


def _confirmed_minutes() -> list[dict[str, object]]:
    return [
        {"timestamp": "2026-06-13 14:50", "open": 10.0, "high": 10.1, "low": 9.98, "close": 10.05, "volume": 1000, "amount": 10050},
        {"timestamp": "2026-06-13 14:51", "open": 10.05, "high": 10.12, "low": 10.01, "close": 10.08, "volume": 1000, "amount": 10080},
        {"timestamp": "2026-06-13 14:52", "open": 10.08, "high": 10.14, "low": 10.03, "close": 10.11, "volume": 1000, "amount": 10110},
        {"timestamp": "2026-06-13 14:53", "open": 10.11, "high": 10.16, "low": 10.05, "close": 10.13, "volume": 1000, "amount": 10130},
        {"timestamp": "2026-06-13 14:54", "open": 10.13, "high": 10.18, "low": 10.07, "close": 10.16, "volume": 1000, "amount": 10160},
    ]
