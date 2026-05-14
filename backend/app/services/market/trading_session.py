from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time as datetime_time

from app.core.timezone import BEIJING_TZ, beijing_now
from app.services.market.trading_calendar import is_a_share_trading_day


_MORNING_OPEN = datetime_time(9, 30)
_MORNING_CLOSE = datetime_time(11, 30)
_AFTERNOON_OPEN = datetime_time(13, 0)
_AFTERNOON_CLOSE = datetime_time(15, 0)


@dataclass(frozen=True)
class TradingSessionStatus:
    is_trading_day: bool
    is_trading_now: bool
    current_time: str
    timezone: str = "Asia/Shanghai"
    data_quality_text: str = "使用后端 A 股交易日历判断。"


def current_a_share_trading_session(now: datetime | None = None) -> TradingSessionStatus:
    current = _normalize_beijing_datetime(now)
    trading_day = is_a_share_trading_day(current.date())
    in_session = trading_day and _in_regular_session(current.time())
    return TradingSessionStatus(
        is_trading_day=trading_day,
        is_trading_now=in_session,
        current_time=current.strftime("%Y-%m-%d %H:%M:%S"),
    )


def _normalize_beijing_datetime(value: datetime | None) -> datetime:
    if value is None:
        return beijing_now()
    if value.tzinfo is None:
        return value.replace(tzinfo=BEIJING_TZ)
    return value.astimezone(BEIJING_TZ)


def _in_regular_session(value: datetime_time) -> bool:
    return (_MORNING_OPEN <= value <= _MORNING_CLOSE) or (_AFTERNOON_OPEN <= value <= _AFTERNOON_CLOSE)
