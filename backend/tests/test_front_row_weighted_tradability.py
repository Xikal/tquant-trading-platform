from __future__ import annotations

from app.services.low_buy.tradability_validation import (
    MinuteExecutionBar,
    TickTrade,
    TradabilityCandidate,
    replay_candidate_tradability,
)


def _candidate() -> TradabilityCandidate:
    return TradabilityCandidate(
        symbol="000001",
        signal_date="2026-06-01",
        entry_trade_date="2026-06-02",
        exit_trade_date="2026-06-03",
        entry_zone_low=9.8,
        entry_zone_high=10.1,
        entry_price=10.0,
        order_amount=1000,
    )


def test_minute_entry_zone_touch_fills() -> None:
    result = replay_candidate_tradability(
        _candidate(),
        minute_bars=[MinuteExecutionBar("2026-06-02", "2026-06-02 09:31:00", 10.0, 10.2, 9.9, 10.1, amount=100000, data_quality="ok")],
    )

    assert result.tradability_status == "filled"
    assert result.reason == "minute_touched_entry_zone"


def test_no_minute_touch_does_not_fill() -> None:
    result = replay_candidate_tradability(
        _candidate(),
        minute_bars=[MinuteExecutionBar("2026-06-02", "2026-06-02 09:31:00", 10.5, 10.8, 10.4, 10.6, amount=100000, data_quality="ok")],
    )

    assert result.tradability_status == "not_filled"
    assert result.reason == "no_entry_zone_touch"


def test_locked_limit_up_blocks_buy() -> None:
    result = replay_candidate_tradability(
        _candidate(),
        minute_bars=[MinuteExecutionBar("2026-06-02", "2026-06-02 09:31:00", 11.0, 11.0, 11.0, 11.0, pct_chg=10.0, amount=100000, data_quality="ok")],
    )

    assert result.tradability_status == "blocked"
    assert result.reason == "locked_limit_up"


def test_tick_path_fills_before_minute_path() -> None:
    result = replay_candidate_tradability(
        _candidate(),
        minute_bars=[MinuteExecutionBar("2026-06-02", "2026-06-02 09:31:00", 10.5, 10.8, 10.4, 10.6, amount=100000, data_quality="ok")],
        tick_trades=[TickTrade("2026-06-02", "2026-06-02 09:30:01", 9.95, amount=100000, data_quality="ok")],
    )

    assert result.tradability_status == "filled"
    assert result.tick_used
    assert result.reason == "tick_touched_entry_zone"
