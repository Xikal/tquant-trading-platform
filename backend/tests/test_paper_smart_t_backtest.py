from __future__ import annotations

from types import SimpleNamespace

from app.services.backtest.data_provider import BacktestSignal, DailyBar
from app.services.paper.smart_t_backtest import collect_smart_t_washout_samples
from app.services.paper.smart_t_strategy_scope import smart_t_backtest_strategy_keys


def test_smart_t_backtest_collects_washout_sample_with_forward_return() -> None:
    signal = BacktestSignal(
        signal_date="2026-05-01",
        symbol="600000",
        strategy_key="first_board",
        name="浦发银行",
        max_holding_days=10,
    )
    bars = [
        _bar("2026-05-01", 10.00, 100),
        _bar("2026-05-02", 9.95, 100),
        _bar("2026-05-03", 9.90, 100),
        _bar("2026-05-04", 9.82, 100),
        _bar("2026-05-05", 9.74, 100),
        _bar("2026-05-06", 9.72, 50),
        _bar("2026-05-07", 9.78, 50),
        _bar("2026-05-08", 9.95, 50),
        _bar("2026-05-09", 10.25, 120),
        _bar("2026-05-10", 10.10, 100),
    ]

    samples = collect_smart_t_washout_samples(
        signals=[signal],
        histories={"600000": bars},
        params={},
        expected_rebound_pct=1.2,
        min_net_profit_pct=0.6,
        forward_days=2,
        context_lookback=8,
    )

    assert len(samples) == 1
    assert samples[0].washout_date == "2026-05-08"
    assert samples[0].success is True
    assert samples[0].forward_max_rebound_pct > 1.2
    assert samples[0].volume_release_ratio < 0.85


def test_smart_t_default_strategy_scope_uses_strategy_metadata(monkeypatch) -> None:
    def fake_list_strategy_meta(self):  # noqa: ANN001, ARG001
        return SimpleNamespace(
            strategies=[
                SimpleNamespace(key="first_board", enabled=True, visibility="full", category_key="core"),
                SimpleNamespace(key="volume_shrink", enabled=True, visibility="full", category_key="auxiliary"),
                SimpleNamespace(key="deep_pullback", enabled=True, visibility="full", category_key="research"),
                SimpleNamespace(key="hidden_strategy", enabled=True, visibility="hidden", category_key="core"),
                SimpleNamespace(key="backtest_only", enabled=True, visibility="backtest_only", category_key="core"),
                SimpleNamespace(key="disabled_strategy", enabled=False, visibility="full", category_key="core"),
            ]
        )

    monkeypatch.setattr(
        "app.services.paper.smart_t_strategy_scope.StrategyMetadataService.list_strategy_meta",
        fake_list_strategy_meta,
    )

    assert smart_t_backtest_strategy_keys(SimpleNamespace()) == ["first_board", "volume_shrink"]


def _bar(trade_date: str, close: float, volume: float) -> DailyBar:
    return DailyBar(
        symbol="600000",
        trade_date=trade_date,
        open_price=close,
        close_price=close,
        high_price=close * 1.01,
        low_price=close * 0.99,
        volume=volume,
        amount=close * volume,
        pct_chg=0.0,
        pre_close=close,
    )
