from __future__ import annotations

from typing import Any, Iterable

from app.services.low_buy.main_force_model_schema import MainForceLabelSnapshot


def build_main_force_labels(
    history_rows: Iterable[Any],
    *,
    as_of_date: str,
    stop_loss_pct: float = -10.0,
    window_20: int = 20,
    window_40: int = 40,
) -> MainForceLabelSnapshot:
    rows = [_normalize_row(row) for row in history_rows]
    rows.sort(key=lambda item: item["trade_date"])
    current = next((row for row in rows if row["trade_date"] == as_of_date), None)
    future = [row for row in rows if row["trade_date"] > as_of_date]
    if current is None or not future or current["close_price"] <= 0:
        return MainForceLabelSnapshot(as_of_date=as_of_date)

    close = current["close_price"]
    future20 = future[:window_20]
    future40 = future[:window_40]
    max20 = _max_return(future20, close)
    max40 = _max_return(future40, close)
    adverse20 = _min_return(future20, close)
    hit_stop = adverse20 <= stop_loss_pct
    return MainForceLabelSnapshot(
        as_of_date=as_of_date,
        label_start_date=future[0]["trade_date"],
        label_end_date=future40[-1]["trade_date"] if future40 else future[-1]["trade_date"],
        max_future_return_20d_pct=round(max20, 4),
        max_future_return_40d_pct=round(max40, 4),
        max_adverse_20d_pct=round(adverse20, 4),
        future_20d_up_30=max20 >= 30.0,
        future_40d_up_50=max40 >= 50.0,
        hit_stop_loss_20d=hit_stop,
        positive_quality_label=max40 >= 50.0 and not hit_stop,
    )


def _normalize_row(row: Any) -> dict[str, Any]:
    getter = row.get if isinstance(row, dict) else lambda key, default=None: getattr(row, key, default)
    return {
        "trade_date": str(getter("trade_date", "") or ""),
        "close_price": _float(getter("close_price", 0.0)),
        "high_price": _float(getter("high_price", getter("close_price", 0.0))),
        "low_price": _float(getter("low_price", getter("close_price", 0.0))),
    }


def _max_return(rows: list[dict[str, Any]], close: float) -> float:
    if not rows or close <= 0:
        return 0.0
    return (max(row["close_price"] for row in rows) / close - 1.0) * 100.0


def _min_return(rows: list[dict[str, Any]], close: float) -> float:
    if not rows or close <= 0:
        return 0.0
    return (min(row["low_price"] for row in rows) / close - 1.0) * 100.0


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
