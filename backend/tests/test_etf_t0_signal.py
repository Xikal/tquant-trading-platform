from __future__ import annotations

from types import SimpleNamespace

from app.models.schemas import KlineBar
from app.services.etf.t0_signal import evaluate_etf_t0_signal
from app.services.sector_etf_t0 import SectorEtfProxy, SectorEtfT0Service


def test_etf_t0_signal_detects_vwap_rsi_reversion_buy() -> None:
    signal = evaluate_etf_t0_signal(
        symbol="510300",
        name="沪深300ETF",
        bars=_bars([10.0] * 17 + [9.95, 9.90, 9.85, 9.86, 9.88]),
        params={"signal_max_trend_slope_abs_pct": 5.0, "signal_min_net_edge_pct": 0.05},
    )

    assert signal.action == "positive_t_buy"
    assert signal.confidence >= 62
    assert signal.t0_eligible is True
    assert signal.vwap > signal.current_price
    assert signal.target_price > signal.current_price
    assert signal.risk_flags == []


def test_etf_t0_signal_detects_vwap_rsi_reversion_sell() -> None:
    signal = evaluate_etf_t0_signal(
        symbol="510300",
        name="沪深300ETF",
        bars=_bars([10.0] * 17 + [10.10, 10.20, 10.30, 10.28, 10.25]),
        params={"signal_max_trend_slope_abs_pct": 5.0, "signal_min_net_edge_pct": 0.05},
    )

    assert signal.action == "negative_t_sell"
    assert signal.confidence >= 62
    assert signal.current_price > signal.vwap
    assert signal.target_price < signal.current_price


def test_etf_t0_signal_blocks_unknown_sector_etf_until_universe_allows_t0() -> None:
    signal = evaluate_etf_t0_signal(
        symbol="512999",
        name="测试行业ETF",
        bars=_bars([10.0] * 22),
    )

    assert signal.action == "hold"
    assert signal.t0_eligible is False
    assert "t0_not_allowed" in signal.risk_flags


def test_etf_t0_signal_blocks_stale_and_wide_spread() -> None:
    stale = evaluate_etf_t0_signal(
        symbol="510300",
        name="沪深300ETF",
        bars=_bars([10.0] * 22),
        data_quality="stale",
    )
    wide_spread = evaluate_etf_t0_signal(
        symbol="510300",
        name="沪深300ETF",
        bars=_bars([10.0] * 17 + [9.95, 9.90, 9.85, 9.86, 9.88]),
        spread_bps=100.0,
        params={"signal_max_trend_slope_abs_pct": 5.0},
    )

    assert stale.action == "hold"
    assert "stale_data" in stale.risk_flags
    assert wide_spread.action == "hold"
    assert "spread_too_wide" in wide_spread.risk_flags


def test_sector_etf_opportunity_embeds_intraday_signal_without_changing_priority_board() -> None:
    bars = _bars([10.0] * 17 + [9.95, 9.90, 9.85, 9.86, 9.88])
    service = SectorEtfT0Service(market_data=_MarketDataStub(bars))
    signal = service._intraday_signal(  # noqa: SLF001
        SectorEtfProxy("510300", "沪深300ETF", ("宽基",)),
        SimpleNamespace(last_price=9.88, data_quality="fresh"),
        params={
            "signal_bar_limit": 30,
            "signal_max_trend_slope_abs_pct": 5.0,
            "signal_min_net_edge_pct": 0.05,
        },
    )

    assert signal is not None
    assert signal.action == "positive_t_buy"
    assert signal.to_dict()["version"] == "etf-t0-signal-v1"


class _MarketDataStub:
    def __init__(self, bars: list[KlineBar]) -> None:
        self._bars = bars

    def get_intraday_bars(self, symbol: str, period: str, limit: int, allow_slow_fallback: bool = False):  # noqa: ARG002
        return self._bars[-limit:]


def _bars(values: list[float]) -> list[KlineBar]:
    result: list[KlineBar] = []
    for index, close in enumerate(values):
        result.append(
            KlineBar(
                timestamp=f"2026-05-27 09:{30 + index:02d}",
                open=close,
                high=round(close * 1.001, 4),
                low=round(close * 0.999, 4),
                close=close,
                volume=1_000_000.0,
                amount=close * 1_000_000.0,
            )
        )
    return result
