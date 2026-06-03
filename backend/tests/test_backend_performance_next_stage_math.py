from __future__ import annotations

import pandas as pd

from app.services.low_buy.atr_metrics import ATR_WINDOW, compute_daily_atr, compute_daily_atr_cached
from app.services.low_buy.history_frames import finalize_daily_history_frame
from app.services.low_buy.main_force_model_features import build_main_force_features
from app.services.read_models.indicator_cache import reset_indicator_cache


def test_history_frame_rust_rolling_mean_matches_pandas_golden() -> None:
    frame = pd.DataFrame(
        [
            {
                "date": f"2026-03-{index + 1:02d}",
                "open": float(index + 1),
                "close": float(index + 1),
                "high": float(index + 1.5),
                "low": float(index + 0.5),
                "volume": 1000 + index,
                "amount": 10000 + index,
                "pct_chg": 0.1,
            }
            for index in range(28)
        ]
    )

    result = finalize_daily_history_frame(frame, "2026-03-01")
    assert result is not None
    for window in (5, 10, 20):
        expected = frame["close"].rolling(window).mean()
        pd.testing.assert_series_equal(result[f"ma{window}"], expected, check_names=False)


def test_cached_atr_matches_original_atr() -> None:
    reset_indicator_cache()
    frame = pd.DataFrame(
        [
            {"high": 10 + index, "low": 9 + index, "close": 9.5 + index}
            for index in range(ATR_WINDOW * 2)
        ]
    )

    assert compute_daily_atr_cached(frame, symbol="000001", trade_date="2026-06-03", period=ATR_WINDOW) == compute_daily_atr(frame, ATR_WINDOW)


def test_main_force_cached_ma_matches_manual_golden() -> None:
    reset_indicator_cache()
    rows = [_bar(f"2026-04-{day:02d}", close=10.0 + day * 0.1) for day in range(1, 25)]

    features = build_main_force_features(rows, symbol="000001", as_of_date="2026-04-24")
    closes = [float(row["close_price"]) for row in rows]

    assert features.ma5 == round(sum(closes[-5:]) / 5, 4)
    assert features.ma10 == round(sum(closes[-10:]) / 10, 4)
    assert features.ma20 == round(sum(closes[-20:]) / 20, 4)


def _bar(trade_date: str, close: float) -> dict[str, float | str]:
    return {
        "trade_date": trade_date,
        "open_price": close * 0.99,
        "close_price": close,
        "high_price": close * 1.02,
        "low_price": close * 0.98,
        "volume": 1_000_000,
        "amount": close * 10_000_000,
        "pct_chg": 0.0,
    }
