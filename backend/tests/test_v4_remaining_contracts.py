from __future__ import annotations

from types import SimpleNamespace
import time
from unittest.mock import patch

from app.models.schema_defs.backtest import default_walk_forward_param_grid
from app.services.backtest.validator import BacktestValidator, ValidationWindow
from app.services.market.providers.quality import MarketDataQuality, ProviderResult
from app.services.market.providers.priority import order_providers_for_operation, provider_execution_tier
from app.services.market.providers.router import MarketProviderRouter
from app.services.paper.quote_quality import PaperQuotePrice


class _Provider:
    def __init__(self, name: str) -> None:
        self.name = name


def test_provider_priority_prefers_healthier_provider() -> None:
    slow = _Provider("slow")
    fast = _Provider("fast")
    snapshot = {
        "providers": {
            "slow:fetch_quote": {"calls": 10, "failures": 5, "slow_calls": 5, "avg_latency_ms": 3000},
            "fast:fetch_quote": {"calls": 10, "failures": 0, "slow_calls": 0, "avg_latency_ms": 20},
        }
    }

    ordered = order_providers_for_operation([slow, fast], snapshot, "fetch_quote")

    assert [item.name for item in ordered] == ["fast", "slow"]


def test_provider_execution_tier_separates_fast_and_slow_sources() -> None:
    assert provider_execution_tier(_Provider("eastmoney")) == "fast"
    assert provider_execution_tier(_Provider("local")) == "fast"
    assert provider_execution_tier(_Provider("akshare")) == "slow"
    assert provider_execution_tier(_Provider("openbb")) == "slow"


def test_provider_router_marks_timed_out_provider_unavailable() -> None:
    class SlowProvider:
        name = "slow_unit_provider"

        def fetch_quote(self, _symbol):
            time.sleep(0.2)
            return ProviderResult(quality=MarketDataQuality.FRESH, source=self.name, data={"late": True})

    router = MarketProviderRouter([SlowProvider()])
    router.call_timeout_seconds = 0.01

    result = router.fetch_quote("600000")

    assert result.quality == MarketDataQuality.UNAVAILABLE
    assert "timed out" in result.message


def test_provider_router_reports_all_providers_circuit_open_only_when_every_provider_open() -> None:
    left = _Provider("left")
    right = _Provider("right")
    router = MarketProviderRouter([left, right])

    assert router.all_providers_circuit_open("fetch_board_breadth_frame") is False

    router.circuits.record("left", "fetch_board_breadth_frame", ok=False, latency_ms=10, error="failed")
    router.circuits.record("left", "fetch_board_breadth_frame", ok=False, latency_ms=10, error="failed")
    router.circuits.record("left", "fetch_board_breadth_frame", ok=False, latency_ms=10, error="failed")

    assert router.all_providers_circuit_open("fetch_board_breadth_frame") is False

    router.circuits.record("right", "fetch_board_breadth_frame", ok=False, latency_ms=10, error="failed")
    router.circuits.record("right", "fetch_board_breadth_frame", ok=False, latency_ms=10, error="failed")
    router.circuits.record("right", "fetch_board_breadth_frame", ok=False, latency_ms=10, error="failed")

    assert router.all_providers_circuit_open("fetch_board_breadth_frame") is True


def test_paper_exit_rejects_stale_quote_quality() -> None:
    from app.services.paper import scheduler_exit

    account = SimpleNamespace(id=1)
    position = SimpleNamespace(symbol="600000")

    class FakePositionService:
        def __init__(self, _db) -> None:
            pass

        def get_positions(self, _account_id):
            return [position]

    with patch.object(scheduler_exit, "PaperPositionService", FakePositionService), patch.object(
        scheduler_exit,
        "latest_prices",
        return_value={"600000": PaperQuotePrice(symbol="600000", price=10.0, quality="stale")},
    ):
        orders, reason = scheduler_exit.build_exit_order_plan(db=object(), account=account)

    assert orders == []
    assert "行情数据不可用" in reason


def test_walk_forward_market_state_summary_includes_best_params() -> None:
    report = BacktestValidator(SimpleNamespace()).walk_forward_windows(
        SimpleNamespace(),
        param_grid=default_walk_forward_param_grid(),
        windows=[],
    )
    assert report.by_market_state == {}

    window = ValidationWindow(
        train_start="2026-01-01",
        train_end="2026-01-10",
        test_start="2026-01-11",
        test_end="2026-01-20",
        train_sharpe=1.0,
        test_sharpe=1.2,
        train_return_pct=2.0,
        test_return_pct=1.0,
        max_drawdown_pct=-1.0,
        best_params={"min_score": 80},
        is_rank=1,
        oos_rank=1,
        passed=True,
        overfit_signal=False,
        market_state_segments=[{"market_state": "repair", "signal_count": 3}],
    )
    summary = BacktestValidator.__module__
    assert summary
    from app.services.backtest.validator import _market_state_summary

    payload = _market_state_summary([window])

    assert payload["repair"]["best_params"] == {"min_score": 80}
