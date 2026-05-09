from __future__ import annotations

import pandas as pd

from app.repositories.low_buy import DailyBarRow


def rows_to_daily_history_frame(rows: list[DailyBarRow], start_date_iso: str) -> pd.DataFrame | None:
    if not rows:
        return None
    normalized = pd.DataFrame(
        [
            {
                "date": row.trade_date,
                "open": row.open_price,
                "close": row.close_price,
                "high": row.high_price,
                "low": row.low_price,
                "volume": row.volume,
                "amount": row.amount,
                "pct_chg": row.pct_chg,
            }
            for row in rows
        ]
    )
    return finalize_daily_history_frame(normalized, start_date_iso)


def frame_to_daily_bar_rows(history: pd.DataFrame) -> list[DailyBarRow]:
    if history.empty:
        return []
    return [
        DailyBarRow(
            trade_date=str(record["date"]),
            open_price=float(record["open"]),
            close_price=float(record["close"]),
            high_price=float(record["high"]),
            low_price=float(record["low"]),
            volume=float(record["volume"]),
            amount=float(record["amount"]),
            pct_chg=float(record["pct_chg"]),
        )
        for record in history.to_dict("records")
    ]


def build_intraday_history_frame(
    history: pd.DataFrame | None,
    *,
    active_trade_date: str,
    quote: object,
) -> pd.DataFrame | None:
    if history is None or history.empty or quote is None or str(history["date"].iloc[-1]) >= active_trade_date:
        return history
    last_price = float(getattr(quote, "last_price", 0.0) or 0.0)
    open_price = float(getattr(quote, "open_price", 0.0) or 0.0)
    high_price = float(getattr(quote, "high_price", 0.0) or 0.0)
    low_price = float(getattr(quote, "low_price", 0.0) or 0.0)
    prev_close = float(getattr(quote, "prev_close", 0.0) or float(history["close"].iloc[-1]) or 0.0)
    volume = float(getattr(quote, "volume", 0.0) or 0.0)
    amount = float(getattr(quote, "amount", 0.0) or 0.0)
    if last_price <= 0:
        return history
    synthetic_bar = {
        "date": active_trade_date,
        "open": open_price if open_price > 0 else prev_close,
        "close": last_price,
        "high": max(high_price, last_price, open_price if open_price > 0 else last_price),
        "low": min(low_price if low_price > 0 else last_price, last_price, open_price if open_price > 0 else last_price),
        "volume": volume,
        "amount": amount,
        "pct_chg": ((last_price / prev_close) - 1) * 100 if prev_close > 0 else 0.0,
    }
    merged = pd.concat([history, pd.DataFrame([synthetic_bar])], ignore_index=True)
    return finalize_daily_history_frame(merged, str(merged["date"].iloc[0]))


def finalize_daily_history_frame(normalized: pd.DataFrame | None, start_date_iso: str) -> pd.DataFrame | None:
    if normalized is None or normalized.empty:
        return None
    normalized = normalized.copy()
    normalized["date"] = normalized["date"].astype(str)
    normalized = normalized[normalized["date"] >= start_date_iso].copy()
    for column in ("open", "close", "high", "low", "volume", "amount", "pct_chg"):
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    normalized = normalized.dropna(subset=["open", "close", "high", "low", "volume", "pct_chg"])
    if normalized.empty:
        return None
    normalized["ma5"] = normalized["close"].rolling(5).mean()
    normalized["ma10"] = normalized["close"].rolling(10).mean()
    normalized["ma20"] = normalized["close"].rolling(20).mean()
    normalized["ma60"] = normalized["close"].rolling(60).mean()
    return normalized.reset_index(drop=True)
