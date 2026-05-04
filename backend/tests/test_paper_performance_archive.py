from __future__ import annotations

import unittest
import json
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.entities import (
    PaperAccount,
    PaperDailyReport,
    PaperMarketPerfDaily,
    PaperOrder,
    PaperPerformanceSnapshot,
    PaperStrategyPerfDaily,
    PaperTrade,
    RiskEvent,
)
from app.services.paper.archive import PaperArchiveService
from app.services.paper.dashboard import PaperPerformanceDashboardService
from app.services.paper.risk_circuit import PaperRiskCircuitBreaker


class PaperPerformanceArchiveTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine, future=True)

    def test_archive_creates_snapshot_tables_without_report(self) -> None:
        with self.Session() as db:
            account = PaperAccount(
                name="测试账户",
                initial_cash=Decimal("100000"),
                cash_available=Decimal("100000"),
                total_assets=Decimal("100000"),
                status="active",
            )
            db.add(account)
            db.commit()
            db.refresh(account)

            result = PaperArchiveService(db).archive_all(account.id, include_report=False)

            self.assertEqual(result["account_id"], account.id)
            self.assertEqual(result["strategies_saved"], 0)
            self.assertEqual(result["market_states_saved"], 0)

    def test_rule_report_is_idempotent(self) -> None:
        with self.Session() as db:
            account = PaperAccount(
                name="测试账户",
                initial_cash=Decimal("100000"),
                cash_available=Decimal("100000"),
                total_assets=Decimal("100000"),
                status="active",
            )
            db.add(account)
            db.commit()
            db.refresh(account)

            service = PaperArchiveService(db)
            first = service.generate_daily_report(account.id, target_date=date.today())
            second = service.generate_daily_report(account.id, target_date=date.today())
            reports = db.execute(select(PaperDailyReport)).scalars().all()

            self.assertEqual(first.id, second.id)
            self.assertEqual(len(reports), 1)
            self.assertIn("模拟盘", second.overall_summary)

    def test_new_archive_models_exist(self) -> None:
        self.assertEqual(PaperStrategyPerfDaily.__tablename__, "paper_strategy_perf_daily")
        self.assertEqual(PaperMarketPerfDaily.__tablename__, "paper_market_perf_daily")
        self.assertEqual(PaperDailyReport.__tablename__, "paper_daily_reports")

    def test_dashboard_service_returns_stable_shape(self) -> None:
        with self.Session() as db:
            account = PaperAccount(
                name="测试账户",
                initial_cash=Decimal("100000"),
                cash_available=Decimal("100000"),
                total_assets=Decimal("100000"),
                status="active",
            )
            db.add(account)
            db.commit()
            db.refresh(account)

            payload = PaperPerformanceDashboardService(db).build(account, days=30)

            self.assertIn("equity_curve", payload)
            self.assertIn("win_rate_trend", payload)
            self.assertIn("strategy_trend", payload)
            self.assertIn("market_perf_heatmap", payload)
            self.assertIn("strategy_market_matrix", payload)

    def test_daily_report_and_snapshot_use_target_date_scope(self) -> None:
        with self.Session() as db:
            account = PaperAccount(
                name="测试账户",
                initial_cash=Decimal("100000"),
                cash_available=Decimal("100000"),
                total_assets=Decimal("100000"),
                status="active",
            )
            db.add(account)
            db.commit()
            db.refresh(account)

            day_one = date(2026, 5, 1)
            day_two = date(2026, 5, 2)
            _add_round_trip(
                db,
                account.id,
                symbol="510300",
                strategy_key="first_board",
                market_state="repair",
                buy_price=Decimal("10"),
                sell_price=Decimal("11"),
                traded_at=datetime(2026, 5, 1, 10, 0),
            )
            _add_round_trip(
                db,
                account.id,
                symbol="159915",
                strategy_key="volume_shrink",
                market_state="risk_release",
                buy_price=Decimal("20"),
                sell_price=Decimal("18"),
                traded_at=datetime(2026, 5, 2, 10, 0),
            )

            result = PaperArchiveService(db).archive_all(account.id, target_date=day_one)
            report = db.execute(select(PaperDailyReport).where(PaperDailyReport.report_date == day_one)).scalar_one()
            snapshot = db.execute(
                select(PaperPerformanceSnapshot).where(PaperPerformanceSnapshot.snapshot_date == day_one)
            ).scalar_one()
            strategy_rows = db.execute(select(PaperStrategyPerfDaily)).scalars().all()
            market_rows = db.execute(select(PaperMarketPerfDaily)).scalars().all()
            metrics = json.loads(report.raw_metrics_snapshot)

            self.assertEqual(result["date"], day_one.isoformat())
            self.assertEqual(snapshot.snapshot_date, day_one)
            self.assertEqual([row.strategy_key for row in strategy_rows], ["first_board"])
            self.assertEqual([row.market_state for row in market_rows], ["repair"])
            self.assertEqual([item["key"] for item in metrics["strategies"]], ["first_board"])
            self.assertEqual([item["key"] for item in metrics["markets"]], ["repair"])
            self.assertEqual(metrics["strategies"][0]["win_rate_pct"], 100.0)

    def test_strategy_market_state_matrix_is_grouped_by_both_dimensions(self) -> None:
        with self.Session() as db:
            account = PaperAccount(
                name="测试账户",
                initial_cash=Decimal("100000"),
                cash_available=Decimal("100000"),
                total_assets=Decimal("100000"),
                status="active",
            )
            db.add(account)
            db.commit()
            db.refresh(account)

            _add_round_trip(
                db,
                account.id,
                symbol="510300",
                strategy_key="first_board",
                market_state="repair",
                buy_price=Decimal("10"),
                sell_price=Decimal("11"),
                traded_at=datetime(2026, 5, 1, 10, 0),
            )
            _add_round_trip(
                db,
                account.id,
                symbol="159915",
                strategy_key="first_board",
                market_state="risk_release",
                buy_price=Decimal("20"),
                sell_price=Decimal("18"),
                traded_at=datetime(2026, 5, 2, 11, 0),
            )

            matrix = PaperArchiveService(db).performance.compute_by_strategy_market_state(account.id)
            recent_matrix = PaperArchiveService(db).performance.compute_by_strategy_market_state(
                account.id,
                start_date=date(2026, 5, 2),
            )

            self.assertEqual({(item["strategy_key"], item["market_state"]) for item in matrix}, {
                ("first_board", "repair"),
                ("first_board", "risk_release"),
            })
            self.assertEqual(
                {(item["strategy_key"], item["market_state"]) for item in recent_matrix},
                {("first_board", "risk_release")},
            )

    def test_three_consecutive_losses_pause_account(self) -> None:
        with self.Session() as db:
            account = PaperAccount(
                name="测试账户",
                initial_cash=Decimal("100000"),
                cash_available=Decimal("100000"),
                total_assets=Decimal("100000"),
                status="active",
            )
            db.add(account)
            db.commit()
            db.refresh(account)

            for index, symbol in enumerate(("510300", "159915", "588000"), start=1):
                _add_round_trip(
                    db,
                    account.id,
                    symbol=symbol,
                    strategy_key="first_board",
                    market_state="repair",
                    buy_price=Decimal("10"),
                    sell_price=Decimal("10") - (Decimal(index) / Decimal("10")),
                    traded_at=datetime(2026, 5, 2, 10, index),
                )

            events = PaperRiskCircuitBreaker(db).evaluate_account(account.id)
            refreshed = db.get(PaperAccount, account.id)
            risk_event = db.execute(select(RiskEvent).where(RiskEvent.event_type == "loss_streak")).scalar_one()

            self.assertEqual(refreshed.status, "paused")
            self.assertEqual(risk_event.severity, "high")
            self.assertTrue(any(item.event_type == "loss_streak" for item in events))


def _add_round_trip(
    db,
    account_id: int,
    *,
    symbol: str,
    strategy_key: str,
    market_state: str,
    buy_price: Decimal,
    sell_price: Decimal,
    traded_at: datetime,
) -> None:
    buy_order = _add_order(db, account_id, symbol, "buy", strategy_key, traded_at)
    sell_order = _add_order(db, account_id, symbol, "sell", strategy_key, traded_at)
    quantity = 100
    db.add_all(
        [
            PaperTrade(
                order_id=buy_order.id,
                account_id=account_id,
                symbol=symbol,
                side="buy",
                price=buy_price,
                quantity=quantity,
                gross_amount=buy_price * quantity,
                net_amount=buy_price * quantity,
                strategy_key=strategy_key,
                market_state=market_state,
                trade_time=traded_at,
            ),
            PaperTrade(
                order_id=sell_order.id,
                account_id=account_id,
                symbol=symbol,
                side="sell",
                price=sell_price,
                quantity=quantity,
                gross_amount=sell_price * quantity,
                net_amount=sell_price * quantity,
                strategy_key=strategy_key,
                market_state=market_state,
                trade_time=traded_at.replace(hour=14),
            ),
        ]
    )
    db.commit()


def _add_order(
    db,
    account_id: int,
    symbol: str,
    side: str,
    strategy_key: str,
    created_at: datetime,
) -> PaperOrder:
    order = PaperOrder(
        account_id=account_id,
        symbol=symbol,
        name=symbol,
        side=side,
        order_type="market",
        quantity=100,
        filled_quantity=100,
        status="filled",
        strategy_key=strategy_key,
        created_at=created_at,
    )
    db.add(order)
    db.flush()
    return order


if __name__ == "__main__":
    unittest.main()
