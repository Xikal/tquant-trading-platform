from __future__ import annotations

from app.models.schema_defs.late_session_board import LateSessionItemState, LateSessionSnapshotSlot
from app.services.low_buy.late_session_board import build_late_session_board


CONFIRMED_MINUTES = [
    {"timestamp": "2026-06-13 14:50", "open": 10.0, "high": 10.1, "low": 9.98, "close": 10.05, "volume": 1000, "amount": 10050},
    {"timestamp": "2026-06-13 14:51", "open": 10.05, "high": 10.12, "low": 10.01, "close": 10.08, "volume": 1000, "amount": 10080},
    {"timestamp": "2026-06-13 14:52", "open": 10.08, "high": 10.14, "low": 10.03, "close": 10.11, "volume": 1000, "amount": 10110},
    {"timestamp": "2026-06-13 14:53", "open": 10.11, "high": 10.16, "low": 10.05, "close": 10.13, "volume": 1000, "amount": 10130},
    {"timestamp": "2026-06-13 14:54", "open": 10.13, "high": 10.18, "low": 10.07, "close": 10.16, "volume": 1000, "amount": 10160},
]


def _candidate(symbol: str = "000001", strategy_key: str = "first_board", production_score: float = 82) -> dict[str, object]:
    return {
        "symbol": symbol,
        "name": "平安银行",
        "strategy_key": strategy_key,
        "priority_score": 88,
        "production_score": production_score,
        "buy_signal_state": "observe",
    }


def test_late_session_board_filters_research_strategy_to_watch() -> None:
    result = build_late_session_board(
        candidates=[_candidate(strategy_key="classic_retrace")],
        minute_bars_by_symbol={"000001": CONFIRMED_MINUTES},
        quotes_by_symbol={"000001": {"latest_price": 10.16, "timestamp": "2026-06-13 14:54:00"}},
        market_state="allow",
        trade_date="2026-06-13",
    )

    assert result.items[0].late_session_state == LateSessionItemState.LATE_WATCH
    assert "research_only" in result.items[0].risk_tags


def test_late_session_board_marks_missing_minutes_unavailable() -> None:
    result = build_late_session_board(
        candidates=[_candidate()],
        minute_bars_by_symbol={},
        quotes_by_symbol={"000001": {"latest_price": 10.16, "timestamp": "2026-06-13 14:54:00"}},
        market_state="allow",
        trade_date="2026-06-13",
    )

    assert result.status == "partial_data"
    assert result.items[0].late_session_state == LateSessionItemState.LATE_UNAVAILABLE
    assert "minute_data_missing" in result.items[0].reject_reasons


def test_late_session_board_rejects_below_vwap() -> None:
    weak_minutes = [dict(row, close=9.7, low=9.65, high=10.2) for row in CONFIRMED_MINUTES]
    result = build_late_session_board(
        candidates=[_candidate()],
        minute_bars_by_symbol={"000001": weak_minutes},
        quotes_by_symbol={"000001": {"latest_price": 9.7, "timestamp": "2026-06-13 14:54:00"}},
        market_state="allow",
        trade_date="2026-06-13",
    )

    assert result.items[0].late_session_state in {
        LateSessionItemState.LATE_WATCH,
        LateSessionItemState.LATE_REJECTED,
    }
    assert result.items[0].late_session_state != LateSessionItemState.LATE_CONFIRMED


def test_late_session_board_market_block_prevents_formal_recommendation() -> None:
    result = build_late_session_board(
        candidates=[_candidate()],
        minute_bars_by_symbol={"000001": CONFIRMED_MINUTES},
        quotes_by_symbol={"000001": {"latest_price": 10.16, "timestamp": "2026-06-13 14:54:00"}},
        market_state="block",
        trade_date="2026-06-13",
    )

    assert result.items[0].late_session_state == LateSessionItemState.LATE_WATCH
    assert "market_block" in result.items[0].reject_reasons


def test_late_session_board_confirms_core_candidate_with_vwap_and_lows() -> None:
    result = build_late_session_board(
        candidates=[_candidate()],
        minute_bars_by_symbol={"000001": CONFIRMED_MINUTES},
        quotes_by_symbol={"000001": {"latest_price": 10.16, "timestamp": "2026-06-13 14:54:00"}},
        market_state="allow",
        trade_date="2026-06-13",
        snapshot_slot=LateSessionSnapshotSlot.SNAPSHOT_1455,
        source_priority_board_epoch="epoch-1",
    )

    item = result.items[0]
    assert result.source_priority_board_epoch == "epoch-1"
    assert item.snapshot_slot == LateSessionSnapshotSlot.SNAPSHOT_1455
    assert item.late_session_state == LateSessionItemState.LATE_CONFIRMED
    assert item.above_vwap is True
    assert item.low_rising is True


def test_late_session_strong_support_score_is_capped() -> None:
    result = build_late_session_board(
        candidates=[_candidate(strategy_key="late_session_strong_support", production_score=99)],
        minute_bars_by_symbol={"000001": CONFIRMED_MINUTES},
        quotes_by_symbol={"000001": {"latest_price": 10.16, "timestamp": "2026-06-13 14:54:00"}},
        market_state="allow",
        trade_date="2026-06-13",
    )

    assert result.items[0].late_session_state == LateSessionItemState.LATE_CONFIRMED
    assert result.items[0].late_session_score == 72.0
