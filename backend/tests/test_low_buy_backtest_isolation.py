from __future__ import annotations

import unittest

from app.repositories.low_buy import DailyBarRow
from scripts.low_buy_market_backtest_reporting import TradeOutcome, backtest_performance_metrics, portfolio_backtest_metrics
from scripts.front_row_weighted_production_scoring_backtest import _decision, _display_variants
from scripts.low_buy_market_backtest import _build_ranked_pools_from_daily_rows, _load_or_build_snapshot


class _DbStub:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


class _BacktestServiceStub:
    def __init__(self, cached_payload=None, computed_payload=None) -> None:
        self.cached_payload = cached_payload
        self.computed_payload = computed_payload or object()
        self.compute_calls = 0
        self.persist_calls = 0

    def _load_materialized_full_result(self, **kwargs):  # noqa: ANN003
        return self.cached_payload

    def _screen_historical_sync(self, **kwargs):  # noqa: ANN003
        self.compute_calls += 1
        return self.computed_payload

    def _persist_materialized_full_result(self, **kwargs) -> None:  # noqa: ANN003
        self.persist_calls += 1
        self.cached_payload = kwargs["payload"]


class LowBuyBacktestIsolationTests(unittest.TestCase):
    def test_isolated_mode_computes_without_persisting_to_production_tables(self) -> None:
        db = _DbStub()
        cached_payload = object()
        service = _BacktestServiceStub(cached_payload=cached_payload)

        payload = _load_or_build_snapshot(
            db=db,
            service=service,
            strategy="classic_retrace",
            trade_date="2026-04-24",
            limit=80,
            scan_limit=480,
            materialization_mode="isolated",
        )

        self.assertIs(payload, service.computed_payload)
        self.assertEqual(service.compute_calls, 1)
        self.assertIsNot(payload, cached_payload)
        self.assertEqual(service.persist_calls, 0)
        self.assertEqual(db.commits, 0)

    def test_read_only_mode_does_not_compute_missing_snapshots(self) -> None:
        service = _BacktestServiceStub()

        payload = _load_or_build_snapshot(
            db=_DbStub(),
            service=service,
            strategy="classic_retrace",
            trade_date="2026-04-24",
            limit=80,
            scan_limit=480,
            materialization_mode="read-only",
        )

        self.assertIsNone(payload)
        self.assertEqual(service.compute_calls, 0)
        self.assertEqual(service.persist_calls, 0)

    def test_production_mode_keeps_explicit_materialization_path(self) -> None:
        db = _DbStub()
        service = _BacktestServiceStub()

        payload = _load_or_build_snapshot(
            db=db,
            service=service,
            strategy="classic_retrace",
            trade_date="2026-04-24",
            limit=80,
            scan_limit=480,
            materialization_mode="production",
        )

        self.assertIs(payload, service.computed_payload)
        self.assertEqual(service.compute_calls, 1)
        self.assertEqual(service.persist_calls, 1)
        self.assertEqual(db.commits, 1)

    def test_fast_backtest_builds_historical_pool_from_daily_rows(self) -> None:
        rows_by_symbol = {
            "000001": [
                _daily_row("2026-04-20", 10.0, 10.0, 10.1, 9.9, 100_000_000),
                _daily_row("2026-04-21", 10.1, 11.1, 11.1, 10.1, 160_000_000, pct_chg=11.0),
                _daily_row("2026-04-22", 11.0, 11.2, 11.3, 10.8, 90_000_000),
            ],
            "510300": [
                _daily_row("2026-04-21", 4.0, 4.4, 4.4, 4.0, 200_000_000, pct_chg=10.0),
            ],
        }

        pools = _build_ranked_pools_from_daily_rows(
            rows_by_symbol=rows_by_symbol,
            trade_dates=["2026-04-20", "2026-04-21", "2026-04-22"],
            evaluation_dates=["2026-04-22"],
            symbol_meta={"000001": ("平安银行", "银行"), "510300": ("沪深300ETF", "")},
        )

        self.assertEqual([item.symbol for item in pools["2026-04-22"]], ["000001"])
        self.assertEqual(pools["2026-04-22"][0].board_date, "2026-04-21")
        self.assertEqual(pools["2026-04-22"][0].board_count, 1)

    def test_performance_metrics_use_capital_limited_daily_signal_curve(self) -> None:
        outcomes = [
            _trade_outcome("2026-04-20", 10.0),
            _trade_outcome("2026-04-20", 10.0),
            _trade_outcome("2026-04-21", 10.0),
        ]

        metrics = backtest_performance_metrics(outcomes)

        self.assertEqual(metrics["trade_count"], 3)
        self.assertEqual(metrics["total_return_pct"], 21.0)
        self.assertEqual(metrics["daily_signal_equal_weight_compound_return_pct"], 21.0)
        self.assertEqual(metrics["diagnostic_compound_return_pct"], 33.1)
        self.assertEqual(metrics["capital_model"], "one_unit_per_signal_day_equal_weight")
        self.assertIn("max_5", metrics["portfolio_backtests"])

    def test_real_portfolio_caps_positions_and_blocks_duplicate_symbol_reentry(self) -> None:
        outcomes = [
            _trade_outcome("2026-04-20", 10.0, symbol="000001", sector_name="人工智能", exit_trade_date="2026-04-23"),
            _trade_outcome("2026-04-21", 8.0, symbol="000001", sector_name="人工智能", exit_trade_date="2026-04-24"),
            _trade_outcome("2026-04-21", 5.0, symbol="000002", sector_name="机器人", exit_trade_date="2026-04-24"),
            _trade_outcome("2026-04-21", 6.0, symbol="000003", sector_name="半导体", exit_trade_date="2026-04-24"),
            _trade_outcome("2026-04-24", 4.0, symbol="000001", sector_name="人工智能", exit_trade_date="2026-04-25"),
        ]

        metrics = portfolio_backtest_metrics(outcomes, max_positions=2)

        self.assertEqual(metrics["capital_model"], "real_portfolio_max_2_equal_slot_no_overlap")
        self.assertEqual(metrics["trade_count"], 3)
        self.assertEqual(metrics["skipped_by_duplicate_symbol"], 1)
        self.assertEqual(metrics["skipped_by_max_positions"], 1)
        self.assertLessEqual(metrics["max_concurrent_positions"], 2)
        self.assertTrue(metrics["capital_occupied_during_holding"])
        self.assertTrue(metrics["available_cash_released_on_exit"])
        self.assertTrue(metrics["same_symbol_reentry_blocked"])

    def test_real_portfolio_applies_strategy_sector_and_market_constraints(self) -> None:
        outcomes = [
            _trade_outcome("2026-04-20", 2.0, symbol="000001", strategy_key="first_board", sector_name="人工智能"),
            _trade_outcome("2026-04-20", 2.0, symbol="000002", strategy_key="first_board", sector_name="人工智能"),
            _trade_outcome("2026-04-20", 2.0, symbol="000003", strategy_key="first_board", sector_name="机器人"),
            _trade_outcome("2026-04-20", 2.0, symbol="000004", strategy_key="volume_shrink", sector_name="人工智能"),
            _trade_outcome("2026-04-21", 2.0, symbol="000005", market_state="high_flyer_retreat"),
        ]

        metrics = portfolio_backtest_metrics(outcomes, max_positions=10)

        self.assertEqual(metrics["trade_count"], 2)
        self.assertEqual(metrics["skipped_by_strategy_daily_limit"], 1)
        self.assertEqual(metrics["skipped_by_sector_limit"], 1)
        self.assertEqual(metrics["skipped_by_retreat_market"], 1)
        self.assertEqual(metrics["skip_reason_counts"]["strategy_daily_limit"], 1)
        self.assertEqual(metrics["skip_reason_counts"]["sector_position_limit"], 1)
        self.assertEqual(metrics["skip_reason_counts"]["retreat_market_no_new_position"], 1)

    def test_real_portfolio_applies_weak_market_position_cap(self) -> None:
        outcomes = [
            _trade_outcome("2026-04-20", 2.0, symbol="000001", strategy_key="first_board", sector_name="人工智能", market_state="low_volume_wait", exit_trade_date="2026-04-23"),
            _trade_outcome("2026-04-20", 2.0, symbol="000002", strategy_key="volume_shrink", sector_name="机器人", market_state="low_volume_wait", exit_trade_date="2026-04-23"),
            _trade_outcome("2026-04-20", 2.0, symbol="000003", strategy_key="ma_support", sector_name="半导体", market_state="low_volume_wait", exit_trade_date="2026-04-23"),
        ]

        metrics = portfolio_backtest_metrics(outcomes, max_positions=5)

        self.assertEqual(metrics["trade_count"], 2)
        self.assertEqual(metrics["skipped_by_weak_market_position_cap"], 1)

    def test_real_portfolio_reports_extra_cost_and_concentration(self) -> None:
        outcomes = [
            _trade_outcome("2026-04-20", 2.0, symbol="000001", sector_name="人工智能"),
            _trade_outcome("2026-04-21", 1.0, symbol="000002", sector_name="机器人"),
            _trade_outcome("2026-04-22", -0.5, symbol="000003", sector_name="半导体"),
        ]

        base = portfolio_backtest_metrics(outcomes, max_positions=5)
        stressed = portfolio_backtest_metrics(outcomes, max_positions=5, extra_cost_bps=50.0)

        self.assertEqual(stressed["extra_cost_bps"], 50.0)
        self.assertLess(stressed["portfolio_return_pct"], base["portfolio_return_pct"])
        self.assertIn("concentration", stressed)
        self.assertIn("top_10_positive_trade_contribution_pct", stressed["concentration"])
        self.assertIn("bootstrap_avg_trade_return_ci95_pct", stressed["concentration"])

    def test_front_row_weighted_decision_does_not_block_on_signal_day_retention_only(self) -> None:
        variants = {
            "baseline": _variant(
                sample_count=100,
                filled_count=100,
                signal_days=100,
                daily_return=0.0,
                max5_return=10.0,
                max10_return=8.0,
                signal_pf=1.1,
                signal_mdd=-20.0,
                portfolio_pf=1.1,
                portfolio_mdd=-10.0,
            ),
            "front_row_weighted_max5": _variant(
                sample_count=30,
                filled_count=30,
                signal_days=40,
                daily_return=20.0,
                max5_return=30.0,
                max10_return=20.0,
                signal_pf=2.0,
                signal_mdd=-8.0,
                portfolio_pf=2.0,
                portfolio_mdd=-5.0,
                oos_signal_days=80,
            ),
            "front_row_weighted_max10": _variant(
                sample_count=30,
                filled_count=30,
                signal_days=40,
                daily_return=20.0,
                max5_return=30.0,
                max10_return=20.0,
                signal_pf=2.0,
                signal_mdd=-8.0,
                portfolio_pf=2.0,
                portfolio_mdd=-5.0,
                oos_signal_days=80,
            ),
            "front_row_only": _variant(sample_count=5, filled_count=5, signal_days=5),
            "front_row_weighted_shadow": _variant(sample_count=100, filled_count=100, signal_days=100),
        }

        decision = _decision(variants)

        self.assertNotIn("signal_day_retention_below_75pct", decision["blockers"])
        self.assertIn("signal_day_retention_below_75pct_precision_mode_warning_only", decision["warnings"])
        self.assertIn("signal_day_retention_below_75pct", decision["deprecated_blockers"])

    def test_display_variants_merge_weighted_max5_and_max10_into_one_candidate_pool(self) -> None:
        variants = {
            "baseline": _variant(sample_count=100, filled_count=90, signal_days=80),
            "front_row_only": _variant(sample_count=10, filled_count=9, signal_days=8),
            "front_row_weighted_shadow": _variant(sample_count=100, filled_count=90, signal_days=80),
            "front_row_weighted_max5": _variant(sample_count=30, filled_count=28, signal_days=20),
            "front_row_weighted_max10": _variant(sample_count=30, filled_count=28, signal_days=20),
        }

        display = _display_variants(variants)

        self.assertIn("front_row_weighted", display)
        self.assertNotIn("front_row_weighted_max5", display)
        self.assertEqual(display["front_row_weighted"]["real_portfolio"]["max5"]["return_pct"], 30.0)
        self.assertEqual(display["front_row_weighted"]["real_portfolio"]["max10"]["return_pct"], 20.0)

    def test_performance_metrics_include_trade_extremes_and_consecutive_losses(self) -> None:
        outcomes = [
            _trade_outcome("2026-04-20", 2.5),
            _trade_outcome("2026-04-21", -1.0),
            _trade_outcome("2026-04-22", -3.2),
            _trade_outcome("2026-04-23", 1.1),
            _trade_outcome("2026-04-24", -0.5),
        ]

        metrics = backtest_performance_metrics(outcomes)

        self.assertEqual(metrics["max_consecutive_loss_count"], 2)
        self.assertEqual(metrics["max_single_loss_pct"], -3.2)
        self.assertEqual(metrics["max_single_gain_pct"], 2.5)


def _trade_outcome(
    signal_date: str,
    net_return_pct: float,
    *,
    symbol: str = "000001",
    exit_trade_date: str | None = None,
    buy_signal_state: str = "buy_now",
    strategy_key: str = "volume_shrink",
    sector_name: str = "测试板块",
    market_state: str = "repair",
) -> TradeOutcome:
    return TradeOutcome(
        symbol=symbol,
        name="测试",
        signal_date=signal_date,
        strategy_key=strategy_key,
        buy_signal_state=buy_signal_state,
        entry_price=10.0,
        execution_status="filled",
        net_return_pct=net_return_pct,
        execution_exit_reason="触发首次止盈位。",
        return_1d=net_return_pct,
        return_2d=net_return_pct,
        return_3d=net_return_pct,
        return_4d=net_return_pct,
        return_5d=net_return_pct,
        max_gain_5d=net_return_pct,
        max_drawdown_5d=0.0,
        entry_trade_date=signal_date,
        exit_trade_date=exit_trade_date or signal_date,
        sector_name=sector_name,
        market_state=market_state,
    )


def _variant(
    *,
    sample_count: int,
    filled_count: int,
    signal_days: int,
    daily_return: float = 0.0,
    max5_return: float = 30.0,
    max10_return: float = 20.0,
    signal_pf: float = 2.0,
    signal_mdd: float = -8.0,
    portfolio_pf: float = 2.0,
    portfolio_mdd: float = -5.0,
    oos_signal_days: int = 80,
) -> dict:
    portfolio5 = {
        "portfolio_return_pct": max5_return,
        "annualized_return_pct": max5_return,
        "max_drawdown_pct": portfolio_mdd,
        "profit_factor": portfolio_pf,
        "win_rate_pct": 55.0,
        "avg_trade_return_pct": 1.0,
        "avg_capital_utilization_pct": 50.0,
        "trade_count": filled_count,
        "skipped_count": 0,
        "max_concurrent_positions": 3,
        "concentration": {
            "top_10_positive_trade_contribution_pct": 40.0,
            "max_symbol_positive_contribution_pct": 10.0,
            "bootstrap_avg_trade_return_ci95_pct": {"low": 0.6, "mid": 1.0, "high": 1.4},
        },
    }
    portfolio10 = {
        **portfolio5,
        "portfolio_return_pct": max10_return,
    }
    return {
        "variant": "test",
        "sample_count": sample_count,
        "filled_count": filled_count,
        "signal_days": signal_days,
        "longest_no_signal_days": 1,
        "daily_signal_equal_weight_compound_return_pct": daily_return,
        "real_portfolio_max5_return_pct": max5_return,
        "real_portfolio_max10_return_pct": max10_return,
        "max_drawdown_pct": signal_mdd,
        "profit_factor": signal_pf,
        "avg_trade_return_pct": 1.0,
        "near_entry_production_score_count": 0,
        "portfolio_max5": portfolio5,
        "portfolio_max10": portfolio10,
        "cost_stress": {
            "extra_cost_30bps": {
                "max5": {"profit_factor": portfolio_pf, "avg_trade_return_pct": 0.7},
                "max10": {"profit_factor": portfolio_pf, "avg_trade_return_pct": 0.7},
            }
        },
        "tradability_proxy": {
            "t1_locked_limit_up_rate_pct": 0.0,
            "t1_open_gap_above_entry_zone_rate_pct": 0.0,
        },
        "by_quarter": [{"key": "2026Q2", "signal_days": oos_signal_days, "sample_count": sample_count, "filled_count": filled_count}],
    }

def _daily_row(
    trade_date: str,
    open_price: float,
    close_price: float,
    high_price: float,
    low_price: float,
    amount: float,
    *,
    pct_chg: float = 0.0,
) -> DailyBarRow:
    return DailyBarRow(
        trade_date=trade_date,
        open_price=open_price,
        close_price=close_price,
        high_price=high_price,
        low_price=low_price,
        volume=1_000_000,
        amount=amount,
        pct_chg=pct_chg,
    )


if __name__ == "__main__":
    unittest.main()
