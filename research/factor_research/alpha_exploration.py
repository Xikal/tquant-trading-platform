from __future__ import annotations

from pathlib import Path

from research.data_sync.tquant_to_qlib import read_offline_table


def summarize_factor_input(path: str | Path) -> dict:
    """Small sanity summary for exported daily bars before factor experiments."""

    frame = read_offline_table(path)
    if frame.empty:
        return {"status": "empty", "rows": 0, "symbols": 0, "start": "", "end": ""}
    return {
        "status": "ok",
        "rows": int(len(frame)),
        "symbols": int(frame["symbol"].nunique()),
        "start": str(frame["trade_date"].min()),
        "end": str(frame["trade_date"].max()),
    }
