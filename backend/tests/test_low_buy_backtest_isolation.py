from __future__ import annotations

import unittest

from app.repositories.low_buy import DailyBarRow
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
