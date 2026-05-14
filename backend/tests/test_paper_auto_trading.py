from __future__ import annotations

import os
import unittest
from collections import namedtuple
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch


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

    def test_position_sizer_uses_kelly_cap(self):
        from app.services.paper.admission import AdmissionResult
        from app.services.low_buy.position_sizing import KellyPosition
        from app.services.paper.sizing import PositionSizer

        candidate = AdmissionResult(
            passed=True,
            symbol="510300",
            priority_score=95,
            reason="通过",
            signal={
                "symbol": "510300",
                "name": "300ETF",
                "latest_price": 10,
                "strategy_key": "first_board",
                "buy_signal_state": "buy_now",
            },
            kelly_position=KellyPosition(
                full_kelly=0.08,
                half_kelly=0.04,
                quarter_kelly=0.02,
                win_rate=0.55,
                avg_win_pct=2.0,
                avg_loss_pct=-1.0,
                expected_value=0.65,
            ),
        )

        result = PositionSizer(max_position_pct=0.10, max_cash_pct=1.0).calculate(
            candidates=[candidate],
            total_assets=100000,
            available_cash=100000,
            max_orders=1,
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].quantity, 400)
        self.assertEqual(result[0].signal_snapshot["position_cap_source"], "kelly_half")

    def test_position_sizer_respects_existing_position_cap(self):
        from app.services.paper.admission import AdmissionResult
        from app.services.paper.sizing import PositionSizer

        candidate = AdmissionResult(
            passed=True,
            symbol="510300",
            priority_score=95,
            reason="通过",
            signal={
                "symbol": "510300",
                "name": "300ETF",
                "latest_price": 10,
                "strategy_key": "first_board",
                "buy_signal_state": "buy_now",
            },
        )

        result = PositionSizer(max_position_pct=0.10, max_cash_pct=1.0).calculate(
            candidates=[candidate],
            total_assets=100000,
            available_cash=100000,
            max_orders=1,
            current_positions={"510300": Decimal("10000")},
        )

        self.assertEqual(result, [])

    def test_position_sizer_uses_volatility_cap(self):
        from app.services.paper.admission import AdmissionResult
        from app.services.paper.sizing import PositionSizer

        candidate = AdmissionResult(
            passed=True,
            symbol="510300",
            priority_score=95,
            reason="通过",
            signal={
                "symbol": "510300",
                "name": "300ETF",
                "latest_price": 10,
                "strategy_key": "first_board",
                "buy_signal_state": "buy_now",
                "final_position_cap_pct": 5.0,
                "volatility_position_pct": 5.0,
                "position_cap_reason": "ATR 高波动，单票仓位上限 5%",
            },
        )

        result = PositionSizer(max_position_pct=0.10, max_cash_pct=1.0).calculate(
            candidates=[candidate],
            total_assets=100000,
            available_cash=100000,
            max_orders=1,
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].quantity, 500)
        self.assertEqual(result[0].signal_snapshot["position_cap_source"], "final_position_cap")

    def test_position_sizer_respects_validation_phase_scale(self):
        from app.services.paper.admission import AdmissionResult
        from app.services.paper.sizing import PositionSizer

        candidate = AdmissionResult(
            passed=True,
            symbol="510300",
            priority_score=95,
            reason="通过",
            signal={
                "symbol": "510300",
                "name": "300ETF",
                "latest_price": 10,
                "strategy_key": "first_board",
                "buy_signal_state": "buy_now",
                "validation_position_scale": 0.2,
                "validation_phase_reason": "Phase 2 小仓验证",
            },
        )

        result = PositionSizer(max_position_pct=0.10, max_cash_pct=1.0).calculate(
            candidates=[candidate],
            total_assets=100000,
            available_cash=100000,
            max_orders=1,
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].quantity, 200)
        self.assertEqual(result[0].signal_snapshot["position_cap_source"], "validation_phase")

    def test_auto_trader_builds_sector_etf_t0_order(self):
        from app.models.schema_defs.market import SectorEtfT0Opportunity, SectorEtfT0Response
        from app.services.paper.scheduler import PaperAutoTrader

        Account = namedtuple("Account", ["id", "cash_available"])
        fake_response = SectorEtfT0Response(
            updated_at="2026-05-08 10:00:00",
            market_state="repair",
            market_state_text="震荡修复",
            total=1,
            opportunities=[
                SectorEtfT0Opportunity(
                    sector_name="半导体",
                    etf_symbol="512480",
                    etf_name="半导体ETF",
                    source_signal_symbol="600000",
                    source_signal_name="测试强信号",
                    source_strategy="first_board",
                    source_signal_text="确定买入",
                    last_price=1.0,
                    bias="positive_t",
                    bias_text="ETF 正T候选",
                    confidence=80,
                    expected_edge_pct=1.2,
                    reason="板块低吸信号明确",
                )
            ],
        )

        class FakeSectorEtfT0Service:
            def __init__(self, **_kwargs):
                pass

            def build_from_priority_board(self, _board, *, limit: int = 8):
                return fake_response

        trader = PaperAutoTrader({"max_orders_per_cycle": 3})
        with patch("app.services.paper.scheduler.SectorEtfT0Service", FakeSectorEtfT0Service):
            orders = trader._build_sector_etf_t0_orders(
                db=None,
                account=Account(id=1, cash_available=Decimal("100000")),
                board={"market_state": "repair", "items": []},
                today_orders=[],
                used_order_count=0,
            )

        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["symbol"], "512480")
        self.assertEqual(orders[0]["strategy_key"], "sector_etf_t0")
        self.assertEqual(orders[0]["source"], "auto_sector_etf_t0")
        self.assertEqual(orders[0]["quantity"], 12000)

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

    def test_auto_exit_orders_skip_when_quotes_unavailable(self):
        from app.services.paper import scheduler_exit

        Account = namedtuple("Account", ["id"])
        Position = namedtuple("Position", ["symbol"])

        class FakePositionService:
            def __init__(self, _db):
                pass

            def get_positions(self, _account_id):
                return [Position(symbol="600000")]

        with patch.object(scheduler_exit, "PaperPositionService", FakePositionService), patch.object(
            scheduler_exit, "latest_prices", return_value={}
        ):
            result = scheduler_exit.build_exit_orders(db=object(), account=Account(id=1))

        self.assertEqual(result, [])

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

    def test_matching_quantizes_stock_and_etf_price_ticks(self):
        from app.services.paper.matching import OrderSide, OrderType, PaperMatchingEngine

        engine = PaperMatchingEngine(slippage_bps=0, etf_slippage_bps=0)
        stock = engine.match(
            symbol="600000",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
            limit_price=None,
            current_price=Decimal("10.1234"),
            quote_time=datetime.now(),
            is_suspended=False,
        )
        etf = engine.match(
            symbol="510300",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
            limit_price=None,
            current_price=Decimal("3.1234"),
            quote_time=datetime.now(),
            is_suspended=False,
        )
        self.assertEqual(stock.avg_fill_price, Decimal("10.12"))
        self.assertEqual(etf.avg_fill_price, Decimal("3.123"))

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
