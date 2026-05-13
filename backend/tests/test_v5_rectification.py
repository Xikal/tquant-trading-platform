from __future__ import annotations

from datetime import datetime
import pandas as pd

from app.services.backtest.regime_walkforward import build_regime_aware_payload
from app.services.backtest.validator import ValidationWindow
from app.services.market.local_quote_cache import local_quote_cache_metrics_snapshot
from app.services.market.providers.circuit import ProviderCircuitConfig, ProviderCircuitRegistry
from app.services.market.providers.circuit_state import ProviderCircuitStore
from app.services.market.providers.local_provider import _daily_history_result
from app.services.market.providers.quality import MarketDataQuality
from app.services.market_quote_cache_refresh import quote_cache_refresh_due
from app.services.portfolio_heuristic_optimizer import (
    HEURISTIC_OPTIMIZER_METHOD,
    LEGACY_MEAN_VARIANCE_ALIAS,
    normalize_optimizer_method,
)
from app.services.position_policy_research import LEGACY_POSITION_POLICY_ALIAS, POSITION_POLICY_ALGORITHM


def test_regime_aware_payload_groups_windows_by_dominant_market_state() -> None:
    windows = [
        ValidationWindow(
            train_start="2026-01-01",
            train_end="2026-02-01",
            test_start="2026-02-02",
            test_end="2026-03-01",
            train_sharpe=1.1,
            test_sharpe=0.8,
            train_return_pct=5.0,
            test_return_pct=2.2,
            max_drawdown_pct=-1.5,
            best_params={"score": 80},
            is_rank=1,
            oos_rank=1,
            passed=True,
            overfit_signal=False,
            train_market_state_segments=[{"name": "修复", "signal_count": 6}],
            market_state_segments=[{"name": "修复", "signal_count": 4}, {"name": "轮动", "signal_count": 1}],
        ),
        ValidationWindow(
            train_start="2026-03-02",
            train_end="2026-04-01",
            test_start="2026-04-02",
            test_end="2026-05-01",
            train_sharpe=0.6,
            test_sharpe=-0.2,
            train_return_pct=1.0,
            test_return_pct=-0.5,
            max_drawdown_pct=-3.2,
            best_params={"score": 72},
            is_rank=1,
            oos_rank=3,
            passed=False,
            overfit_signal=True,
            train_market_state_segments=[{"name": "震荡", "signal_count": 3}],
            market_state_segments=[{"name": "震荡", "signal_count": 5}],
        ),
    ]

    by_state, best_params_by_state, details = build_regime_aware_payload(windows)

    assert by_state["修复"]["window_count"] == 1
    assert by_state["修复"]["pass_rate"] == 1.0
    assert by_state["震荡"]["failed_windows"] == 1
    assert best_params_by_state["修复"] == {"score": 80}
    assert details["震荡"][0]["train_market_state"] == "震荡"


def test_local_provider_short_history_returns_usable_quality() -> None:
    frame = pd.DataFrame(
        [
            {"date": f"2026-01-{day:02d}", "open": 1.0, "close": 1.0, "high": 1.0, "low": 1.0, "volume": 1.0, "amount": 1.0, "pct_chg": 0.0}
            for day in range(1, 31)
        ]
    )
    result = _daily_history_result(frame, "2026-03-01")
    assert result.quality == MarketDataQuality.ESTIMATED
    assert result.usable is True
    assert "limited_history" in result.message


def test_optimizer_method_alias_is_not_exposed_as_mean_variance() -> None:
    assert normalize_optimizer_method(LEGACY_MEAN_VARIANCE_ALIAS) == HEURISTIC_OPTIMIZER_METHOD


def test_position_policy_research_uses_non_rl_algorithm_name() -> None:
    assert POSITION_POLICY_ALGORITHM != LEGACY_POSITION_POLICY_ALIAS


def test_provider_circuit_registry_supports_isolated_store() -> None:
    store_a = ProviderCircuitStore()
    store_b = ProviderCircuitStore()
    registry_a = ProviderCircuitRegistry(ProviderCircuitConfig(failure_threshold=1), store=store_a)
    registry_b = ProviderCircuitRegistry(ProviderCircuitConfig(failure_threshold=1), store=store_b)

    registry_a.record("unit", "quote", ok=False, latency_ms=10, error="timeout")

    assert "unit:quote" in registry_a.snapshot()["providers"]
    assert "unit:quote" not in registry_b.snapshot()["providers"]


def test_quote_cache_refresh_due_respects_trading_session() -> None:
    assert quote_cache_refresh_due(datetime(2026, 5, 11, 9, 40)) is True
    assert quote_cache_refresh_due(datetime(2026, 5, 11, 12, 0)) is False
    assert quote_cache_refresh_due(datetime(2026, 5, 10, 10, 0)) is False


def test_local_quote_cache_metrics_snapshot_shape() -> None:
    snapshot = local_quote_cache_metrics_snapshot()
    assert {"reads", "hits", "writes", "misses"}.issubset(snapshot.keys())
