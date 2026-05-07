from __future__ import annotations

import os
import unittest
from collections import namedtuple
from datetime import date, datetime
from decimal import Decimal


class PaperAutoTradingTest(unittest.TestCase):
    def test_imports_work(self):
        from app.services.paper.admission import AdmissionFilter, AdmissionResult
        from app.services.paper.scheduler import AutoTraderState, PaperAutoTrader
        from app.services.paper.sizing import PositionSizer, SizedOrder

        self.assertTrue(callable(AdmissionFilter))
        self.assertTrue(callable(AdmissionResult))
        self.assertTrue(callable(PositionSizer))
        self.assertTrue(callable(SizedOrder))
        self.assertTrue(callable(PaperAutoTrader))
        self.assertTrue(callable(AutoTraderState))

    def test_admission_filter_empty(self):
        from app.services.paper.admission import AdmissionFilter

        result = AdmissionFilter(min_score=75).evaluate(
            signals=[],
            existing_positions=[],
            today_orders=[],
            market_direction="positive_t",
        )
        self.assertEqual(result.passed, [])
        self.assertEqual(result.filtered, [])
        self.assertEqual(result.summary, "无优先级信号")

    def test_admission_score_too_low(self):
        from app.services.paper.admission import AdmissionFilter

        signal = {
            "symbol": "000001",
            "name": "测试",
            "priority_score": 60,
            "risk_tier": "note",
            "buy_signal_state": "buy_now",
        }
        result = AdmissionFilter(min_score=75).evaluate(
            signals=[signal],
            existing_positions=[],
            today_orders=[],
            market_direction="positive_t",
        )
        self.assertEqual(len(result.passed), 0)
        self.assertIn("调度分60<阈值75", result.filtered[0].reason)

    def test_admission_market_negative(self):
        from app.services.paper.admission import AdmissionFilter

        signal = {
            "symbol": "000001",
            "name": "测试",
            "priority_score": 82,
            "risk_tier": "note",
            "buy_signal_state": "buy_now",
        }
        result = AdmissionFilter(min_score=75).evaluate(
            signals=[signal],
            existing_positions=[],
            today_orders=[],
            market_direction="negative_t",
        )
        self.assertEqual(len(result.passed), 0)
        self.assertIn("退潮", result.filtered[0].reason)

    def test_admission_rejects_chinext_and_star_market_stocks(self):
        from app.services.paper.admission import AdmissionFilter

        result = AdmissionFilter(min_score=75).evaluate(
            signals=[
                {
                    "symbol": "300059",
                    "name": "东方财富",
                    "priority_score": 95,
                    "risk_tier": "note",
                    "buy_signal_state": "buy_now",
                },
                {
                    "symbol": "688981",
                    "name": "中芯国际",
                    "priority_score": 95,
                    "risk_tier": "note",
                    "buy_signal_state": "buy_now",
                },
            ],
            existing_positions=[],
            today_orders=[],
            market_direction="positive_t",
        )

        self.assertEqual(len(result.passed), 0)
        self.assertTrue(all("创业板/科创板" in item.reason for item in result.filtered))

    def test_admission_rejects_same_day_filled_order(self):
        from app.services.paper.admission import AdmissionFilter

        signal = {
            "symbol": "000001",
            "name": "测试",
            "priority_score": 88,
            "risk_tier": "note",
            "buy_signal_state": "buy_now",
        }
        result = AdmissionFilter(min_score=75).evaluate(
            signals=[signal],
            existing_positions=[],
            today_orders=[{"symbol": "000001", "status": "filled", "side": "buy"}],
            market_direction="positive_t",
        )
        self.assertEqual(len(result.passed), 0)
        self.assertIn("今日已买入", result.filtered[0].reason)

    def test_position_sizer_empty(self):
        from app.services.paper.sizing import PositionSizer

        result = PositionSizer().calculate(
            candidates=[],
            total_assets=0,
            available_cash=0,
            max_orders=5,
        )
        self.assertEqual(result, [])

    def test_position_sizer_normal(self):
        from app.services.paper.sizing import PositionSizer

        Candidate = namedtuple("Candidate", ["symbol", "name", "priority_score", "signal"])
        candidates = [
            Candidate(
                "510300",
                "300ETF",
                85,
                {
                    "symbol": "510300",
                    "name": "300ETF",
                    "latest_price": 3.478,
                    "strategy_key": "first_board",
                    "buy_signal_state": "buy_now",
                    "risk_tier": "note",
                },
            )
        ]
        result = PositionSizer().calculate(
            candidates=candidates,
            total_assets=100000,
            available_cash=50000,
            max_orders=5,
        )
        self.assertEqual(len(result), 1)
        self.assertGreaterEqual(result[0].quantity, 100)
        self.assertEqual(result[0].quantity % 100, 0)
        self.assertEqual(result[0].source, "auto")

    def test_auto_trader_trading_time(self):
        from app.services.paper.scheduler import PaperAutoTrader

        trader = PaperAutoTrader({})
        self.assertFalse(trader._is_trading_time(datetime(2026, 5, 2, 10, 0)))
        self.assertFalse(trader._is_trading_time(datetime(2026, 5, 4, 10, 0)))
        self.assertTrue(trader._is_trading_time(datetime(2026, 5, 6, 10, 0)))
        self.assertFalse(trader._is_trading_time(datetime(2026, 5, 6, 15, 0)))

    def test_auto_trader_state_init(self):
        from app.services.paper.scheduler import PaperAutoTrader

        trader = PaperAutoTrader(
            {
                "dry_run": True,
                "interval_seconds": 120,
                "max_orders_per_cycle": 5,
                "min_score": 75,
            }
        )
        self.assertTrue(trader.state.dry_run)
        self.assertFalse(trader.state.running)
        self.assertEqual(trader.state.interval_seconds, 120)
        self.assertEqual(trader.state.max_orders_per_cycle, 5)
        self.assertEqual(trader.state.min_score, 75)

    def test_config_defaults(self):
        from app.core.config import get_settings

        original_enabled = os.environ.get("PAPER_AUTO_TRADING_ENABLED")
        original_dry_run = os.environ.get("PAPER_AUTO_TRADING_DRY_RUN")
        os.environ["PAPER_AUTO_TRADING_ENABLED"] = "true"
        os.environ["PAPER_AUTO_TRADING_DRY_RUN"] = "false"
        get_settings.cache_clear()
        try:
            settings = get_settings()
            self.assertTrue(settings.paper_auto_trading_enabled)
            self.assertFalse(settings.paper_auto_trading_dry_run)
        finally:
            if original_enabled is None:
                os.environ.pop("PAPER_AUTO_TRADING_ENABLED", None)
            else:
                os.environ["PAPER_AUTO_TRADING_ENABLED"] = original_enabled
            if original_dry_run is None:
                os.environ.pop("PAPER_AUTO_TRADING_DRY_RUN", None)
            else:
                os.environ["PAPER_AUTO_TRADING_DRY_RUN"] = original_dry_run
            get_settings.cache_clear()

    def test_module_trading_time_helper(self):
        from app.services.paper.scheduler import is_trading_time

        self.assertFalse(is_trading_time(datetime(2026, 5, 2, 10, 0)))
        self.assertFalse(is_trading_time(datetime(2026, 5, 4, 10, 0)))
        self.assertTrue(is_trading_time(datetime(2026, 5, 6, 10, 0)))
        self.assertFalse(is_trading_time(datetime(2026, 5, 6, 15, 0)))

    def test_blocked_run_dedupes_same_reason_in_recent_window(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        from app.models.base import Base
        from app.models.entities import PaperAccount, PaperAgentRun
        from app.services.paper.scheduler import PaperAutoTrader

        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine, future=True)
        with Session() as db:
            account = PaperAccount(name="测试账户", initial_cash=Decimal("100000"), cash_available=Decimal("100000"), total_assets=Decimal("100000"))
            db.add(account)
            db.commit()
            db.refresh(account)
            reason = "模拟盘最大回撤 -28.50%，建议暂停新增委托并复盘。"
            db.add(
                PaperAgentRun(
                    account_id=account.id,
                    provider="paper_auto_trader",
                    run_type="auto_trade_cycle",
                    status="skipped",
                    response_json=f'{{"skipped":[{{"account_id":{account.id},"reason":"{reason}"}}]}}',
                    created_at=datetime.now(),
                )
            )
            db.commit()

            trader = PaperAutoTrader({})
            self.assertFalse(trader._should_persist_blocked_run(db, account_id=account.id, blocking_reason=reason))
            self.assertTrue(trader._should_persist_blocked_run(db, account_id=account.id, blocking_reason="另一条风控原因"))

    def test_matching_rejects_invalid_prices(self):
        from app.services.paper.matching import OrderSide, OrderType, PaperMatchingEngine

        result = PaperMatchingEngine().match(
            symbol="510300",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
            limit_price=None,
            current_price=Decimal("0"),
            quote_time=datetime.now(),
            is_suspended=False,
        )
        self.assertEqual(result.result, "rejected")
        self.assertIn("价格无效", result.reject_reason or "")

    def test_next_business_day_skips_cn_market_holidays(self):
        from app.services.market.trading_calendar import last_a_share_trading_day, next_a_share_trading_day

        self.assertEqual(next_a_share_trading_day(date(2025, 12, 31)), date(2026, 1, 2))
        self.assertEqual(last_a_share_trading_day(date(2026, 5, 3)), date(2026, 4, 30))

    def test_planned_order_format(self):
        from app.services.paper.sizing import PositionSizer

        Candidate = namedtuple("Candidate", ["symbol", "name", "priority_score", "signal"])
        candidates = [
            Candidate(
                "510300",
                "300ETF",
                82,
                {
                    "symbol": "510300",
                    "name": "300ETF",
                    "latest_price": 3.5,
                    "strategy_key": "first_board",
                    "buy_signal_state": "buy_now",
                    "risk_tier": "note",
                },
            )
        ]
        result = PositionSizer().calculate(candidates=candidates, total_assets=100000, available_cash=50000, max_orders=1)
        self.assertEqual(len(result), 1)
        plan = result[0].to_plan_dict()
        for field_name in ("symbol", "name", "side", "order_type", "quantity", "price", "source", "strategy_key"):
            self.assertIn(field_name, plan)

    def test_executor_dry_run_respects_max_orders_without_creating_orders(self):
        from app.services.paper.executor import PaperTradingExecutor

        class DummyDb:
            def __init__(self):
                self.commits = 0
                self.rollbacks = 0

            def commit(self):
                self.commits += 1

            def rollback(self):
                self.rollbacks += 1

        class FailingOrderService:
            def __init__(self):
                self.db = DummyDb()

            def create_order(self, **_kwargs):
                raise AssertionError("dry_run must not create paper orders")

        order_service = FailingOrderService()
        planned_orders = [
            {"symbol": "510300", "quantity": 100},
            {"symbol": "159915", "quantity": 100},
            {"symbol": "588000", "quantity": 100},
        ]

        result = PaperTradingExecutor(order_service).execute_plan(
            account_id=1,
            planned_orders=planned_orders,
            max_orders=2,
            dry_run=True,
        )

        self.assertEqual(result["executed"], [])
        self.assertEqual([item["symbol"] for item in result["skipped"]], ["510300", "159915"])
        self.assertEqual(result["summary"], "执行 0 条，跳过 2 条。")
        self.assertEqual(order_service.db.commits, 1)
        self.assertEqual(order_service.db.rollbacks, 0)


if __name__ == "__main__":
    unittest.main()
