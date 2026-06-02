from __future__ import annotations

import unittest
from collections import namedtuple
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from app.core.timezone import beijing_now


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

    def test_strategy_phase_gate_injects_scale_before_sizing(self):
        from app.services.paper.admission import AdmissionResult
        from app.services.paper.sizing import PositionSizer
        from app.services.paper.strategy_phase_gate import apply_strategy_validation_phase

        phase = namedtuple("Phase", "phase phase_text reason position_scale")
        candidate = AdmissionResult(
            passed=True,
            symbol="510300",
            priority_score=95,
            reason="通过",
            signal={"symbol": "510300", "latest_price": 10, "strategy_key": "first_board"},
        )
        with patch("app.services.paper.strategy_phase_gate.latest_strategy_performance_map", return_value={}):
            with patch("app.services.paper.strategy_phase_gate.strategy_health", return_value=(70.0, [])):
                with patch(
                    "app.services.paper.strategy_phase_gate.resolve_strategy_validation_phase",
                    return_value=phase("phase2", "Phase 2 小仓验证", "小仓验证", 0.2),
                ):
                    passed, filtered = apply_strategy_validation_phase(object(), [candidate])

        self.assertEqual(filtered, [])
        orders = PositionSizer(max_position_pct=0.10, max_cash_pct=1.0).calculate(
            candidates=passed,
            total_assets=100000,
            available_cash=100000,
            max_orders=1,
        )
        self.assertEqual(orders[0].quantity, 200)
        self.assertEqual(orders[0].signal_snapshot["validation_position_scale"], 0.2)

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
                    t0_eligible=True,
                    intraday_signal_action="positive_t_buy",
                    intraday_signal_confidence=78,
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

    def test_auto_trader_skips_sector_etf_without_intraday_positive_t_signal(self):
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
                    source_signal_text="确定买入",
                    last_price=1.0,
                    bias="positive_t",
                    bias_text="ETF 正T候选",
                    t0_eligible=True,
                    intraday_signal_action="hold",
                    intraday_signal_confidence=80,
                    intraday_risk_flags=["edge_too_small"],
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

        self.assertEqual(orders, [])

    def test_auto_trader_skips_sector_etf_without_t0_eligibility(self):
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
                    sector_name="测试行业",
                    etf_symbol="512999",
                    etf_name="测试行业ETF",
                    source_signal_symbol="600000",
                    source_signal_name="测试强信号",
                    source_signal_text="确定买入",
                    last_price=1.0,
                    bias="positive_t",
                    bias_text="ETF 正T候选",
                    t0_eligible=False,
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

        self.assertEqual(orders, [])

    def test_blocked_run_dedupes_same_reason_in_recent_window(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        from app.models.base import Base
        from app.models.entities import PaperAccount, PaperAgentRun, RiskEvent
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
                    created_at=beijing_now().replace(tzinfo=None),
                )
            )
            db.commit()

            trader = PaperAutoTrader({})
            self.assertFalse(trader._should_persist_blocked_run(db, account_id=account.id, blocking_reason=reason))
            self.assertTrue(trader._should_persist_blocked_run(db, account_id=account.id, blocking_reason="另一条风控原因"))

            db.add_all(
                [
                    RiskEvent(
                        account_id=account.id,
                        event_type="regime_jump_position_review",
                        severity="high",
                        status="open",
                        message="旧风险提示",
                    ),
                    RiskEvent(
                        account_id=account.id,
                        event_type="regime_jump_position_review",
                        severity="high",
                        status="open",
                        message="最新风险提示",
                    ),
                ]
            )
            db.commit()

            self.assertEqual(trader._blocking_reason(db, account.id), "最新风险提示")

    def test_blocked_account_still_executes_auto_exit_orders(self):
        from app.services.paper.scheduler import PaperAutoTrader

        Account = namedtuple("Account", ["id"])
        trader = PaperAutoTrader({"dry_run": False})
        exit_orders = [
            {
                "symbol": "600000",
                "name": "测试",
                "side": "sell",
                "order_type": "market",
                "quantity": 100,
                "price": 10.5,
                "current_price": 10.5,
                "source": "auto_exit",
                "strategy_key": "first_board",
                "reason": "动态止损",
                "signal_snapshot": {"exit_code": "hard_stop_loss"},
            }
        ]
        captured = {}

        def fake_build_exit_order_plan(_db, _account):
            return exit_orders, ""

        def fake_execute_orders(*, db, account_id, orders):
            captured["account_id"] = account_id
            captured["orders"] = orders
            return {"executed": [{"order_id": 1, "symbol": "600000", "status": "filled"}], "skipped": []}

        trader._build_exit_order_plan = fake_build_exit_order_plan
        trader._execute_orders = fake_execute_orders

        result = trader._build_and_execute_blocked_exit_plan(
            db=object(),
            account=Account(id=7),
            blocking_reason="账户存在高风险事件",
        )

        self.assertEqual(captured["account_id"], 7)
        self.assertEqual(captured["orders"], exit_orders)
        self.assertEqual(result["exit_order_count"], 1)
        self.assertEqual(result["buy_order_count"], 0)
        self.assertEqual(result["executed"][0]["symbol"], "600000")
        self.assertIn("已优先执行自动退出", result["summary"])

    def test_blocked_account_reports_auto_exit_quote_skip_reason(self):
        from app.services.paper.scheduler import PaperAutoTrader

        Account = namedtuple("Account", ["id"])
        trader = PaperAutoTrader({"dry_run": False})

        def fake_build_exit_order_plan(_db, _account):
            return [], "自动退出暂停：行情数据不可用，等待下轮刷新。"

        trader._build_exit_order_plan = fake_build_exit_order_plan

        result = trader._build_and_execute_blocked_exit_plan(
            db=object(),
            account=Account(id=7),
            blocking_reason="账户存在高风险事件",
        )

        self.assertEqual(result["executed"], [])
        self.assertEqual(result["exit_order_count"], 0)
        self.assertEqual(result["skipped"][0]["source"], "auto_exit")
        self.assertIn("行情数据不可用", result["skipped"][0]["reason"])

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
            quote_time=beijing_now().replace(tzinfo=None),
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
            quote_time=beijing_now().replace(tzinfo=None),
            is_suspended=False,
        )
        etf = engine.match(
            symbol="510300",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
            limit_price=None,
            current_price=Decimal("3.1234"),
            quote_time=beijing_now().replace(tzinfo=None),
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
