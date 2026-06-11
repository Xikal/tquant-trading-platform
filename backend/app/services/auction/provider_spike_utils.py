from __future__ import annotations

import time
from datetime import datetime, time as datetime_time
from typing import Any, Callable, Iterable

from app.core.timezone import BEIJING_TZ
from app.services.market.trading_calendar import is_a_share_trading_day

WINDOW_START = datetime_time(9, 19, 30)
WINDOW_END = datetime_time(9, 25, 30)
PROCESS_START = datetime_time(9, 20, 0)
RESULT_START = datetime_time(9, 25, 0)


def build_window_status(
    now: datetime,
    window_type: type,
    *,
    is_trading_day_func: Callable[[Any], bool] = is_a_share_trading_day,
) -> Any:
    current = normalize_beijing_datetime(now)
    trade_date = current.date()
    trading_day = bool(is_trading_day_func(trade_date))
    in_window = trading_day and WINDOW_START <= current.time() <= WINDOW_END
    if not trading_day:
        status = "non_trading_day"
        message = "当前不是 A 股交易日，G0 只能生成 blocked 报告。"
    elif current.time() < WINDOW_START:
        status = "before_spike_window"
        message = "当前早于 9:19:30，尚不能验证集合竞价 provider。"
    elif current.time() > WINDOW_END:
        status = "after_spike_window"
        message = "当前晚于 9:25:30，已错过本次集合竞价 provider spike 窗口。"
    else:
        status = "in_spike_window"
        message = "当前位于 9:19:30-9:25:30 provider spike 窗口。"
    return window_type(
        status=status,
        in_window=in_window,
        is_trading_day=trading_day,
        checked_at=current.isoformat(timespec="seconds"),
        trade_date=trade_date.isoformat(),
        window_start=WINDOW_START.isoformat(),
        window_end=WINDOW_END.isoformat(),
        message=message,
    )


def parse_beijing_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return normalize_beijing_datetime(parsed)


def normalize_beijing_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=BEIJING_TZ)
    return value.astimezone(BEIJING_TZ)


def extract_row_time(row: dict[str, Any]) -> datetime_time | None:
    raw = first_present(row, "时间", "日期", "datetime", "date", "time", "timestamp")
    if raw in (None, ""):
        return None
    text = str(raw).strip().replace("/", "-")
    candidates = (
        text,
        text[:19],
        text[:16],
        text[-8:],
        text[-5:],
    )
    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M",
        "%H:%M:%S",
        "%H:%M",
    )
    for candidate in candidates:
        if not candidate:
            continue
        if "-" in candidate and ":" in candidate:
            try:
                return datetime.fromisoformat(candidate).time()
            except ValueError:
                pass
        for date_format in formats:
            try:
                return datetime.strptime(candidate, date_format).time()
            except ValueError:
                continue
    return None


def row_has_any(row: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return first_present(row, *keys) not in (None, "")


def first_present(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, "", "-", "--"):
            return row[key]
    return ""


def dedupe_symbols(symbols: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in symbols:
        symbol = str(raw or "").strip()
        if len(symbol) != 6 or not symbol.isdigit() or symbol in seen:
            continue
        seen.add(symbol)
        result.append(symbol)
    return result


def classify_bucket(symbol: str) -> str:
    if instrument_type_for_symbol(symbol) == "etf":
        return "etf"
    if symbol.startswith("6"):
        return "sh_stock"
    if symbol.startswith(("0", "3")):
        return "sz_stock"
    return "other"


def market_for_symbol(symbol: str) -> str:
    return "SH" if symbol.startswith(("5", "6", "9")) else "SZ"


def instrument_type_for_symbol(symbol: str) -> str:
    if symbol.startswith(("51", "52", "56", "58", "15")):
        return "etf"
    return "stock"


def latency_ms(started: float) -> int:
    return int(round((time.perf_counter() - started) * 1000))


def json_safe_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {str(key): json_safe(value) for key, value in row.items()}


def json_safe(value: Any) -> Any:
    if value in (None, "", "-", "--"):
        return ""
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
