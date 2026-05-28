from __future__ import annotations

from app.services.low_buy.main_force_model_features import build_main_force_features
from app.services.low_buy.main_force_model_labels import build_main_force_labels
from backend.tests.main_force_model_test_helpers import washout_history


def test_main_force_temporal_guard_max_source_date_and_label_start() -> None:
    history = washout_history() + [
        {
            "trade_date": "2026-04-27",
            "open_price": 12.0,
            "close_price": 16.0,
            "high_price": 16.5,
            "low_price": 11.8,
            "volume": 3_000_000,
            "amount": 480_000_000,
            "pct_chg": 30.0,
            "future_return_20d": 80.0,
        }
    ]

    features = build_main_force_features(history, symbol="300001", as_of_date="2026-04-24")
    labels = build_main_force_labels(history, as_of_date="2026-04-24")

    assert features.max_source_date <= features.as_of_date
    assert labels.label_start_date > labels.as_of_date
    assert "future_return_20d" not in features.feature_values


def test_t_plus_one_price_does_not_change_t_day_features() -> None:
    base = washout_history()
    with_future = base + [
        {
            "trade_date": "2026-04-27",
            "open_price": 12.0,
            "close_price": 20.0,
            "high_price": 21.0,
            "low_price": 11.8,
            "volume": 9_000_000,
            "amount": 1_800_000_000,
            "pct_chg": 70.0,
        }
    ]

    before = build_main_force_features(base, symbol="300001", as_of_date="2026-04-24")
    after = build_main_force_features(with_future, symbol="300001", as_of_date="2026-04-24")

    assert before.to_dict() == after.to_dict()
