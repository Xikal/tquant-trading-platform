from __future__ import annotations

from datetime import datetime

from app.services.market.trading_session import current_a_share_trading_session


def test_afternoon_close_instant_is_not_trading() -> None:
    status = current_a_share_trading_session(datetime(2026, 5, 6, 15, 0, 0))

    assert status.is_trading_day is True
    assert status.is_trading_now is False


def test_one_second_before_afternoon_close_is_trading() -> None:
    status = current_a_share_trading_session(datetime(2026, 5, 6, 14, 59, 59))

    assert status.is_trading_day is True
    assert status.is_trading_now is True
