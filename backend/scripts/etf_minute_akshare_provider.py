from __future__ import annotations

import os
from typing import Any

import requests

from app.core.config import BASE_ENV_PATH, RUNTIME_ENV_PATH
from app.models.schemas import KlineBar
from dotenv import dotenv_values

try:
    import akshare as ak  # type: ignore
except Exception:  # pragma: no cover
    ak = None


def fetch_tushare_etf_hist_minute_bars(*, symbol: str, start_date: str, end_date: str, period: str) -> list[KlineBar]:
    token = tushare_token()
    if not token:
        raise RuntimeError("tushare token not configured")
    payload = {
        "api_name": "stk_mins",
        "token": token,
        "params": {
            "ts_code": tushare_ts_code(symbol),
            "freq": period.lower(),
            "start_date": f"{start_date} 09:00:00",
            "end_date": f"{end_date} 15:00:00",
        },
        "fields": "ts_code,trade_time,open,close,high,low,vol,amount",
    }
    response = requests.post("https://api.tushare.pro", json=payload, timeout=20)
    response.raise_for_status()
    payload_json = response.json()
    if int(payload_json.get("code") or 0) != 0:
        raise RuntimeError(f"tushare stk_mins failed: {str(payload_json.get('msg') or '')[:160]}")
    data = payload_json.get("data") or {}
    fields = [str(item) for item in data.get("fields") or []]
    items = data.get("items") or []
    return parse_tushare_etf_minute_records([dict(zip(fields, item)) for item in items])


def fetch_akshare_etf_hist_minute_bars(*, symbol: str, start_date: str, end_date: str, period: str) -> list[KlineBar]:
    if ak is None:
        raise RuntimeError("akshare unavailable")
    frame = ak.fund_etf_hist_min_em(
        symbol=symbol,
        start_date=f"{start_date} 09:30:00",
        end_date=f"{end_date} 15:00:00",
        period=period.removesuffix("m"),
        adjust="",
    )
    if frame is None or getattr(frame, "empty", False):
        return []
    return parse_akshare_etf_minute_records(frame.to_dict("records"))


def parse_tushare_etf_minute_records(records: list[dict[str, Any]]) -> list[KlineBar]:
    bars: list[KlineBar] = []
    for raw in records:
        bars.append(
            build_bar(
                timestamp=str(raw.get("trade_time") or raw.get("time") or ""),
                open_value=raw.get("open"),
                close_value=raw.get("close"),
                high_value=raw.get("high"),
                low_value=raw.get("low"),
                volume=raw.get("vol"),
                amount=raw.get("amount"),
            )
        )
    return [bar for bar in bars if bar.close > 0]


def parse_akshare_etf_minute_records(records: list[dict[str, Any]]) -> list[KlineBar]:
    bars: list[KlineBar] = []
    for raw in records:
        timestamp = first_present(raw, "时间", "日期", "datetime", "date", "day")
        bars.append(
            build_bar(
                timestamp=str(timestamp),
                open_value=first_present(raw, "开盘", "open"),
                close_value=first_present(raw, "收盘", "close", "最新价"),
                high_value=first_present(raw, "最高", "high"),
                low_value=first_present(raw, "最低", "low"),
                volume=first_present(raw, "成交量", "volume"),
                amount=first_present(raw, "成交额", "amount"),
            )
        )
    return [bar for bar in bars if bar.close > 0]


def first_present(raw: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = raw.get(key)
        if value not in (None, "", "-", "--"):
            return value
    return ""


def build_bar(*, timestamp: str, open_value: Any, close_value: Any, high_value: Any, low_value: Any, volume: Any, amount: Any) -> KlineBar:
    close_float = safe_float(close_value)
    return KlineBar(
        timestamp=timestamp[:16],
        open=safe_float(open_value) or close_float,
        close=close_float,
        high=safe_float(high_value) or close_float,
        low=safe_float(low_value) or close_float,
        volume=safe_float(volume),
        amount=safe_float(amount),
    )


def tushare_ts_code(symbol: str) -> str:
    suffix = "SH" if symbol.startswith(("5", "6", "9")) else "SZ"
    return f"{symbol}.{suffix}"


def tushare_token() -> str:
    for key in ("TUSHARE_TOKEN", "TUSHARE_API_TOKEN", "TUSHARE_PRO_TOKEN"):
        value = os.getenv(key)
        if value:
            return value.strip()
    for path in (BASE_ENV_PATH, RUNTIME_ENV_PATH):
        if not path.exists():
            continue
        values = dotenv_values(path)
        for key in ("TUSHARE_TOKEN", "TUSHARE_API_TOKEN", "TUSHARE_PRO_TOKEN"):
            value = values.get(key)
            if value:
                return value.strip()
    return ""


def safe_float(value: Any) -> float:
    try:
        if value in (None, "", "-", "--"):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0
