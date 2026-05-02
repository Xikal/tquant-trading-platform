from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.entities import (
    LowBuyPoolSnapshot,
    LowBuyResultSnapshot,
    LowBuyScanSnapshot,
    LowBuyStrategyPoolSnapshot,
)
from app.repositories.low_buy import (
    DailyBarRow,
    DailyHistoryRepository,
    LowBuyPerformanceRepository,
    LowBuyPoolRepository,
    LowBuyResultRepository,
    LowBuyStrategyPoolRepository,
    SystemSettingRepository,
)


class LowBuyRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, future=True)

    def test_daily_history_upsert_and_fetch(self) -> None:
        with self.Session() as db:
            repo = DailyHistoryRepository(db)
            repo.upsert_rows(
                "000001",
                [
                    DailyBarRow("2026-04-18", 10.0, 10.5, 10.6, 9.9, 1000, 2000, 1.2),
                    DailyBarRow("2026-04-19", 10.5, 10.2, 10.7, 10.1, 1200, 2400, -0.6),
                ],
            )
            db.commit()
            rows = repo.fetch_rows("000001", "2026-04-18", "2026-04-19")
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0].trade_date, "2026-04-18")
            self.assertAlmostEqual(rows[1].close_price, 10.2)

    def test_pool_repository_replace(self) -> None:
        with self.Session() as db:
            repo = LowBuyPoolRepository(db)
            repo.replace(
                "2026-04-19",
                [
                    LowBuyPoolSnapshot(
                        latest_trade_date="2026-04-19",
                        symbol="000001",
                        name="平安银行",
                        board_date="2026-04-17",
                        board_count=1,
                        amount=100000000,
                        industry="银行",
                    )
                ],
            )
            db.commit()
            rows = repo.fetch("2026-04-19")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].symbol, "000001")

    def test_strategy_pool_repository_keeps_strategy_pools_isolated(self) -> None:
        with self.Session() as db:
            repo = LowBuyStrategyPoolRepository(db)
            base = {
                "latest_trade_date": "2026-04-19",
                "pool_key": "mainline_daily_pool",
                "name": "测试股",
                "industry": "人工智能",
                "anchor_date": "2026-04-17",
                "anchor_type": "daily_history",
                "rank_score": 1.0,
                "amount": 100000000,
                "board_count": 1,
            }
            repo.replace(
                latest_trade_date="2026-04-19",
                pool_key="mainline_daily_pool",
                strategy_key="late_session_strong_support",
                rows=[
                    LowBuyStrategyPoolSnapshot(
                        **base,
                        strategy_key="late_session_strong_support",
                        symbol="300001",
                    )
                ],
            )
            repo.replace(
                latest_trade_date="2026-04-19",
                pool_key="mainline_daily_pool",
                strategy_key="core_midcap_vwap_ma5_retrace",
                rows=[
                    LowBuyStrategyPoolSnapshot(
                        **base,
                        strategy_key="core_midcap_vwap_ma5_retrace",
                        symbol="300002",
                    )
                ],
            )
            db.commit()

            late_rows = repo.fetch(
                latest_trade_date="2026-04-19",
                pool_key="mainline_daily_pool",
                strategy_key="late_session_strong_support",
            )
            core_rows = repo.fetch(
                latest_trade_date="2026-04-19",
                pool_key="mainline_daily_pool",
                strategy_key="core_midcap_vwap_ma5_retrace",
            )

            self.assertEqual([row.symbol for row in late_rows], ["300001"])
            self.assertEqual([row.symbol for row in core_rows], ["300002"])

    def test_results_repository_replace_and_fetch(self) -> None:
        with self.Session() as db:
            repo = LowBuyResultRepository(db)
            repo.replace_materialized_scan(
                latest_trade_date="2026-04-19",
                strategy_key="classic_retrace",
                summary=LowBuyScanSnapshot(
                    latest_trade_date="2026-04-19",
                    strategy_key="classic_retrace",
                    strategy_title="原始低吸法",
                    strategy_subtitle="测试",
                    strategy_logic="测试",
                    as_of_date="2026-04-19 15:00:00",
                    pool_size=10,
                    scanned_count=10,
                    matched_count=1,
                    requested_scan_limit=10,
                    active_scan_limit=10,
                    retracement_distribution_json="{}",
                    filters_json="{}",
                    strategy_notes_json="[]",
                ),
                results=[
                    LowBuyResultSnapshot(
                        latest_trade_date="2026-04-19",
                        strategy_key="classic_retrace",
                        symbol="000001",
                        name="平安银行",
                        score=88.0,
                        buy_signal_state="buy_now",
                        payload_json="{}",
                    )
                ],
            )
            db.commit()
            summary = repo.fetch_scan_summary("2026-04-19", "classic_retrace")
            rows = repo.fetch_confirmed_results("2026-04-19", "classic_retrace", 10)
            self.assertIsNotNone(summary)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].symbol, "000001")

    def test_system_setting_upsert(self) -> None:
        with self.Session() as db:
            repo = SystemSettingRepository(db)
            repo.upsert("demo:key", "value-1")
            db.commit()
            self.assertEqual(repo.fetch("demo:key").value, "value-1")
            repo.upsert("demo:key", "value-2")
            db.commit()
            self.assertEqual(repo.fetch("demo:key").value, "value-2")

    def test_performance_repository_keeps_multiple_lookback_windows(self) -> None:
        with self.Session() as db:
            repo = LowBuyPerformanceRepository(db)
            values_60 = {
                "lookback_days": 60,
                "signal_count": 12,
                "evaluated_signals": 10,
                "pending_signals": 2,
                "hit_count": 5,
                "hit_rate": 50.0,
                "win_rate_1d": 55.0,
                "win_rate_3d": 58.0,
                "win_rate_5d": 60.0,
                "avg_return_1d": 1.2,
                "avg_return_3d": 2.1,
                "avg_return_5d": 3.0,
                "avg_max_gain_5d": 4.8,
                "avg_max_drawdown_5d": -2.2,
                "payload_json": "{\"lookback_days\":60}",
            }
            values_20 = dict(values_60)
            values_20["lookback_days"] = 20
            values_20["payload_json"] = "{\"lookback_days\":20}"
            repo.save("2026-04-19", "classic_retrace", 60, values_60)
            repo.save("2026-04-19", "classic_retrace", 20, values_20)
            db.commit()

            row_60 = repo.fetch("2026-04-19", "classic_retrace", 60)
            row_20 = repo.fetch("2026-04-19", "classic_retrace", 20)
            self.assertIsNotNone(row_60)
            self.assertIsNotNone(row_20)
            self.assertEqual(row_60.lookback_days, 60)
            self.assertEqual(row_20.lookback_days, 20)


if __name__ == "__main__":
    unittest.main()
