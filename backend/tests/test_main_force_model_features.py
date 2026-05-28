from __future__ import annotations

from app.services.low_buy.main_force_model_advisor import MainForceAdvisor
from app.services.low_buy.main_force_model_features import build_main_force_features


def test_main_force_features_ignore_future_rows_for_same_as_of_date() -> None:
    history = _history_with_washout()

    features = build_main_force_features(
        history,
        symbol="300001",
        name="测试科技",
        as_of_date="2026-04-24",
        market_state="repair",
        sector_strength=0.74,
    )
    with_future = build_main_force_features(
        history
        + [
            _bar("2026-04-27", 11.5, 14.2, 14.5, 11.4, 18_000_000, 240_000_000, 22.41),
            _bar("2026-04-28", 14.3, 16.6, 17.0, 14.2, 25_000_000, 390_000_000, 16.90),
        ],
        symbol="300001",
        name="测试科技",
        as_of_date="2026-04-24",
        market_state="repair",
        sector_strength=0.74,
    )

    assert features.max_source_date == "2026-04-24"
    assert with_future.max_source_date == "2026-04-24"
    assert with_future.to_dict() == features.to_dict()


def test_main_force_advisor_returns_shadow_buy_probe_for_quality_washout() -> None:
    features = build_main_force_features(
        _history_with_washout(),
        symbol="300001",
        name="测试科技",
        as_of_date="2026-04-24",
        strategy_key="volume_shrink",
        market_state="repair",
        sector_strength=0.76,
    )

    advice = MainForceAdvisor().advise(features)

    assert advice.shadow_only is True
    assert advice.action in {"buy_probe", "buy_confirmed"}
    assert advice.stage in {"washout", "markup_confirm"}
    assert advice.score >= 55
    assert advice.production_effect == "none"
    assert advice.feature_snapshot["max_source_date"] == "2026-04-24"
    assert advice.buy_zone[0] < advice.buy_zone[1]
    assert advice.stop_loss > 0


def test_main_force_advisor_blocks_distribution_risk_without_touching_candidate() -> None:
    features = build_main_force_features(
        _history_with_distribution_risk(),
        symbol="300002",
        name="测试风险",
        as_of_date="2026-04-24",
        strategy_key="n_pattern_short_wash",
        market_state="high_flyer_retreat",
        sector_strength=0.22,
    )

    advice = MainForceAdvisor().advise(features)

    assert advice.shadow_only is True
    assert advice.action == "blocked"
    assert advice.production_effect == "none"
    assert advice.risk_flags
    assert any("退潮" in reason or "出货" in reason or "放量滞涨" in reason for reason in advice.risk_flags)


def test_main_force_advisor_can_annotate_plain_candidate_without_mutating_it() -> None:
    candidate = {
        "symbol": "300001",
        "name": "测试科技",
        "score": 88.0,
        "buy_signal_state": "near_entry",
        "strategy_key": "volume_shrink",
    }
    original = dict(candidate)
    features = build_main_force_features(
        _history_with_washout(),
        symbol="300001",
        name="测试科技",
        as_of_date="2026-04-24",
        strategy_key="volume_shrink",
        market_state="repair",
        sector_strength=0.76,
    )

    annotated = MainForceAdvisor().annotate_candidate(candidate, features)

    assert candidate == original
    assert annotated["symbol"] == candidate["symbol"]
    assert annotated["score"] == candidate["score"]
    assert annotated["main_force_advice"]["shadow_only"] is True
    assert annotated["main_force_advice"]["production_effect"] == "none"


def _history_with_washout() -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    price = 10.0
    for idx in range(45):
        day = idx + 1
        trade_date = f"2026-03-{day:02d}" if day <= 31 else f"2026-04-{day - 31:02d}"
        if idx < 22:
            close = price + idx * 0.03
            volume = 1_000_000 + idx * 8_000
        elif idx < 30:
            close = 10.9 + (idx - 22) * 0.22
            volume = 2_700_000 + (idx - 22) * 120_000
        elif idx < 41:
            close = 12.4 - (idx - 30) * 0.11
            volume = 1_250_000 - min(idx - 30, 8) * 45_000
        else:
            close = 11.25 + (idx - 41) * 0.12
            volume = 1_500_000 + (idx - 41) * 110_000
        rows.append(_bar(trade_date, close * 0.99, close, close * 1.025, close * 0.975, volume, volume * close * 10, 0.0))
    rows[-1]["trade_date"] = "2026-04-24"
    rows[-1]["close_price"] = 11.72
    rows[-1]["high_price"] = 11.86
    rows[-1]["low_price"] = 11.18
    rows[-1]["open_price"] = 11.28
    rows[-1]["amount"] = 210_000_000
    rows[-1]["volume"] = 1_760_000
    rows[-1]["pct_chg"] = 3.2
    return rows


def _history_with_distribution_risk() -> list[dict[str, float | str]]:
    rows = _history_with_washout()
    for idx, row in enumerate(rows[-8:]):
        row["close_price"] = 16.0 + idx * 0.08
        row["open_price"] = 15.8 + idx * 0.08
        row["high_price"] = 18.0 + idx * 0.12
        row["low_price"] = 15.5 + idx * 0.08
        row["volume"] = 5_000_000 + idx * 500_000
        row["amount"] = 850_000_000 + idx * 80_000_000
        row["pct_chg"] = -1.8 if idx >= 6 else 2.5
    rows[-1]["trade_date"] = "2026-04-24"
    rows[-1]["close_price"] = 16.1
    rows[-1]["high_price"] = 19.5
    rows[-1]["low_price"] = 15.9
    rows[-1]["open_price"] = 18.8
    rows[-1]["pct_chg"] = -5.2
    rows[-1]["amount"] = 1_500_000_000
    return rows


def _bar(
    trade_date: str,
    open_price: float,
    close_price: float,
    high_price: float,
    low_price: float,
    volume: float,
    amount: float,
    pct_chg: float,
) -> dict[str, float | str]:
    return {
        "trade_date": trade_date,
        "open_price": open_price,
        "close_price": close_price,
        "high_price": high_price,
        "low_price": low_price,
        "volume": volume,
        "amount": amount,
        "pct_chg": pct_chg,
    }
