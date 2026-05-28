from __future__ import annotations

from app.services.low_buy.main_force_model_features import build_main_force_features
from app.services.low_buy.main_force_model_labels import build_main_force_labels


def test_main_force_labels_use_only_rows_after_as_of_date() -> None:
    history = [
        _bar("2026-04-20", 10.0),
        _bar("2026-04-21", 10.2),
        _bar("2026-04-22", 10.1),
        _bar("2026-04-23", 10.3),
        _bar("2026-04-24", 10.0),
        _bar("2026-04-27", 11.0),
        _bar("2026-04-28", 12.0),
        _bar("2026-04-29", 15.5),
    ]

    labels = build_main_force_labels(history, as_of_date="2026-04-24", stop_loss_pct=-8.0)

    assert labels.as_of_date == "2026-04-24"
    assert labels.label_start_date == "2026-04-27"
    assert labels.max_future_return_20d_pct == 55.0
    assert labels.future_20d_up_30 is True
    assert labels.future_40d_up_50 is True


def test_main_force_features_do_not_change_when_labels_become_positive() -> None:
    base = [_bar(f"2026-04-{day:02d}", 10.0 + day * 0.02) for day in range(1, 25)]
    future_winner = base + [_bar("2026-04-25", 18.0)]

    before = build_main_force_features(base, symbol="300001", as_of_date="2026-04-24")
    after = build_main_force_features(future_winner, symbol="300001", as_of_date="2026-04-24")
    labels = build_main_force_labels(future_winner, as_of_date="2026-04-24")

    assert labels.future_20d_up_30 is True
    assert before.to_dict() == after.to_dict()


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
