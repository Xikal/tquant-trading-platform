from __future__ import annotations

import tempfile
import unittest
from os import environ
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.base import Base
from app.models.entities import DailyBarSnapshot, LowBuyResultSnapshot, LowBuyScanSnapshot, SystemSetting
from app.models.schemas import LowBuyCandidateOut, LowBuyExecutionBacktestItemOut, LowBuyStrategyPerformanceOut, SettingsUpdate
from app.repositories.low_buy.lifecycle import LowBuyTradeLifecycleRepository
from app.services.low_buy.candidate_rules import build_strategy_setup
from app.services.low_buy.exit_plan import build_exit_plan
from app.services.low_buy.hard_risk import build_hard_risk_assessment
from app.services.low_buy.portfolio_risk import build_portfolio_risk
from app.services.low_buy.service import LowBuyScreenerService
from app.services.low_buy.shared import LOW_BUY_RESULT_VERSION
from app.services.low_buy.dynamic_adjustments import apply_performance_adjustment_to_candidate
from app.services.low_buy.execution_backtest import _build_backtest_response
from app.services.low_buy.strategy_policy import participates_in_priority_board
from app.services.settings_service import SettingsService
from backend.tests.test_divergence_consensus_strategy import _item, _metrics


class LowBuyTradeControlTests(unittest.TestCase):
    def test_hard_risk_blocks_st_and_low_liquidity(self) -> None:
        st_result = build_hard_risk_assessment(
            item=_item(name="*ST测试"),
            metrics=_metrics(),
        )
        low_liquidity_result = build_hard_risk_assessment(
            item=_item(amount=50_000_000),
            metrics=_metrics(),
        )

        self.assertEqual(st_result.level, "block")
        self.assertTrue(st_result.execution_blocked)
        self.assertEqual(low_liquidity_result.level, "block")

    def test_divergence_exit_plan_uses_right_side_failure_rules(self) -> None:
        metrics = _metrics()
        strategy_setup = build_strategy_setup("divergence_consensus", _item(), metrics, 93.0)
        setup = build_exit_plan(
            strategy="divergence_consensus",
            metrics=metrics,
            setup=strategy_setup,
            stop_loss=9.6,
            take_profit=11.0,
        )

        self.assertIn("分歧高点", setup.invalid_condition)
        self.assertGreaterEqual(setup.trailing_stop, setup.stop_loss)
        self.assertLessEqual(setup.max_holding_days, 5)

    def test_core_low_buy_plans_use_three_day_protection(self) -> None:
        metrics = _metrics()
        setup = build_strategy_setup("volume_shrink", _item(), metrics, 91.0)
        exit_plan = build_exit_plan(
            strategy="volume_shrink",
            metrics=metrics,
            setup=setup,
            stop_loss=9.4,
            take_profit=10.8,
        )

        self.assertEqual(exit_plan.max_holding_days, 3)
        self.assertIn("3 个交易日", exit_plan.time_stop_text)
        self.assertTrue(any("3%-5%" in rule for rule in exit_plan.exit_rules))

    def test_unstable_strategies_are_demoted_from_strong_buy(self) -> None:
        screener = LowBuyScreenerService()
        paused = (
            "limit_up_breakout_retrace",
            "classic_retrace",
            "ma_support",
            "breakout_support",
            "divergence_consensus",
            "deep_pullback",
            "trend_rebound",
        )
        for strategy in paused:
            candidate = _candidate(strategy_key=strategy, score=96.0)
            updated = screener._resolve_signal_state(
                candidate=candidate,
                entry_position="in_zone",
                entry_distance=0.0,
                hard_confirmed=True,
                soft_confirmed=True,
                historical=True,
                confirmed_trade_date="2026-04-20",
            )
            self.assertEqual(updated.buy_signal_state, "near_entry")
            self.assertNotIn(updated.buy_signal_state, {"buy_now", "soft_buy_now"})

    def test_priority_board_policy_only_includes_production_strategies(self) -> None:
        production = (
            "first_board",
            "volume_shrink",
            "late_session_strong_support",
            "core_midcap_vwap_ma5_retrace",
            "sector_mainline_first_divergence_low_buy",
        )
        demoted = (
            "limit_up_breakout_retrace",
            "classic_retrace",
            "ma_support",
            "breakout_support",
            "divergence_consensus",
            "deep_pullback",
            "trend_rebound",
        )
        for strategy in production:
            self.assertTrue(participates_in_priority_board(strategy), strategy)
        for strategy in demoted:
            self.assertFalse(participates_in_priority_board(strategy), strategy)

    def test_small_filled_sample_does_not_boost_strategy_weight_or_position(self) -> None:
        service = LowBuyScreenerService()
        performance = LowBuyStrategyPerformanceOut(
            lookback_days=120,
            evaluated_signals=80,
            filled_signals=3,
            hit_count=3,
            hit_rate=100,
            net_win_rate=100,
            avg_net_return_pct=8.0,
            avg_return_3d=8.0,
            avg_return_5d=8.0,
        )
        candidate = _candidate()

        self.assertEqual(service._strategy_weight_score(performance, None), 40.0)
        adjusted = apply_performance_adjustment_to_candidate(candidate, performance)
        self.assertEqual(adjusted.dynamic_position_multiplier, candidate.dynamic_position_multiplier)

    def test_portfolio_risk_flags_industry_concentration(self) -> None:
        candidates = [
            _candidate(symbol="000001", sector_name="人工智能", position=18),
            _candidate(symbol="000002", sector_name="人工智能", position=16),
        ]
        risk = build_portfolio_risk(candidates, market_state="low_volume_wait")

        self.assertEqual(risk.top_industry, "人工智能")
        self.assertGreaterEqual(risk.industry_concentration_pct, 30)
        self.assertIn(risk.risk_level, {"degrade", "block"})

    def test_execution_backtest_uses_entry_exit_cost_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = create_engine(f"sqlite:///{Path(tmpdir) / 'test.db'}", future=True)
            Base.metadata.create_all(engine)
            SessionLocal = sessionmaker(bind=engine, future=True)
            with SessionLocal() as db:
                candidate = _candidate(symbol="000001", position=20)
                _seed_scan(db, candidate)
                _seed_daily_rows(db, candidate.symbol)
                result = LowBuyScreenerService().execution_backtest(
                    db=db,
                    strategy="classic_retrace",
                    lookback_days=10,
                    limit=10,
                )

        self.assertEqual(result.evaluated_signals, 1)
        self.assertEqual(result.filled_signals, 1)
        self.assertGreater(result.avg_net_return_pct, 0)

    def test_execution_backtest_net_win_rate_is_net_edge_not_win_rate(self) -> None:
        result = _build_backtest_response(
            strategy="first_board",
            lookback_days=5,
            items=[
                _backtest_item(net_return_pct=1.2, exit_reason="止盈", max_gain_pct=2.0, max_drawdown_pct=-0.8),
                _backtest_item(net_return_pct=-0.6, exit_reason="止损", max_gain_pct=0.5, max_drawdown_pct=-1.4),
                _backtest_item(net_return_pct=0.0, exit_reason="最长持有", max_gain_pct=0.4, max_drawdown_pct=-0.5),
            ],
        )

        self.assertEqual(result.win_rate, 33.333)
        self.assertEqual(result.net_win_rate, 0.0)

    def test_lifecycle_sync_preserves_execution_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = create_engine(f"sqlite:///{Path(tmpdir) / 'test.db'}", future=True)
            Base.metadata.create_all(engine)
            SessionLocal = sessionmaker(bind=engine, future=True)
            with SessionLocal() as db:
                repository = LowBuyTradeLifecycleRepository(db)
                row = repository.upsert_planned(_lifecycle_values(entry_high=10.1))
                row.status = "entered"
                row.entry_price = 10.0
                row.entry_trade_date = "2026-04-21"
                db.commit()

                repository.upsert_planned(_lifecycle_values(entry_high=10.3, name="新名称"))
                db.commit()
                fetched = repository.fetch_one(
                    signal_trade_date="2026-04-20",
                    strategy_key="classic_retrace",
                    symbol="000001",
                )

        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.status, "entered")
        self.assertEqual(fetched.entry_price, 10.0)
        self.assertEqual(fetched.name, "新名称")
        self.assertEqual(fetched.entry_plan_high, 10.3)

    def test_settings_public_payload_masks_secrets_and_preserves_masked_updates(self) -> None:
        original_secret = environ.get("AUTH_SECRET_KEY")
        environ["AUTH_SECRET_KEY"] = "settings-test-secret-0123456789abcdef0123456789abcdef0123456789abcdef"
        get_settings.cache_clear()
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                runtime_env_path = tmp_path / "runtime.env"
                runtime_env_path.write_text(
                    'LLM_API_KEY="old-plain-key"\nLLM_MODEL="qwen-old"\n',
                    encoding="utf-8",
                )
                engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", future=True)
                Base.metadata.create_all(engine)
                SessionLocal = sessionmaker(bind=engine, future=True)
                with patch("app.services.settings_service.RUNTIME_ENV_PATH", runtime_env_path):
                    with SessionLocal() as db:
                        service = SettingsService(db)
                        service.update_payload(
                            SettingsUpdate(
                                llm_api_key="sk-test-secret",
                                database_url="mysql+pymysql://root:db-secret@localhost/app",
                            )
                        )
                        public = service.get_public_payload(admin_auth_required=True)
                        service.update_payload(
                            SettingsUpdate(
                                llm_api_key=public.llm_api_key,
                                database_url=public.database_url,
                                llm_model="qwen-plus",
                            )
                        )
                        raw = service.get_payload()
                        stored_api_key = db.execute(
                            select(SystemSetting).where(SystemSetting.key == "llm_api_key")
                        ).scalar_one()
                        stored_database_url = db.execute(
                            select(SystemSetting).where(SystemSetting.key == "database_url")
                        ).scalar_one()
                        runtime_text = runtime_env_path.read_text(encoding="utf-8")
        finally:
            if original_secret is None:
                environ.pop("AUTH_SECRET_KEY", None)
            else:
                environ["AUTH_SECRET_KEY"] = original_secret
            get_settings.cache_clear()

        self.assertEqual(public.llm_api_key, "********")
        self.assertNotIn("db-secret", public.database_url)
        self.assertEqual(raw.llm_api_key, "sk-test-secret")
        self.assertIn("db-secret", raw.database_url)
        self.assertEqual(raw.llm_model, "qwen-plus")
        self.assertIsNotNone(stored_api_key)
        self.assertIsNotNone(stored_database_url)
        self.assertNotIn("sk-test-secret", stored_api_key.value)
        self.assertNotIn("db-secret", stored_database_url.value)
        self.assertNotIn("LLM_API_KEY", runtime_text)
        self.assertNotIn("old-plain-key", runtime_text)
        self.assertNotIn("sk-test-secret", runtime_text)
        self.assertIn("DATABASE_URL", runtime_text)
        self.assertIn("LLM_MODEL", runtime_text)
        self.assertTrue(stored_api_key.value.startswith("enc:v1:"))
        self.assertTrue(stored_database_url.value.startswith("enc:v1:"))


def _candidate(
    symbol: str = "000001",
    sector_name: str = "人工智能",
    position: float = 20,
    strategy_key: str = "classic_retrace",
    score: float = 91.0,
) -> LowBuyCandidateOut:
    return LowBuyCandidateOut(
        strategy_key=strategy_key,
        strategy_title="原始低吸法",
        payload_version=LOW_BUY_RESULT_VERSION,
        symbol=symbol,
        name="测试股份",
        market="CN",
        instrument_type="stock",
        sector_name=sector_name,
        latest_price=10.0,
        change_pct=0.0,
        quote_timestamp="2026-04-20",
        board_date="2026-04-15",
        board_count=1,
        retracement_days=3,
        score=score,
        entry_zone_low=9.8,
        entry_zone_high=10.1,
        stop_loss=9.4,
        take_profit=10.7,
        ma5=10.0,
        ma10=9.9,
        ma20=9.6,
        volume_burst_ratio=2.0,
        volume_shrink_ratio=0.6,
        support_distance_pct=1.2,
        execution_ready=True,
        execution_note="结构满足",
        trigger_condition="价格进入买点区",
        invalid_condition="跌破止损",
        entry_distance_pct=0.0,
        suggested_position_pct=position,
        suggested_position_text="先试仓",
        market_state="broad_rally",
        market_state_text="普涨扩散",
        market_state_strength=0.2,
        market_position_multiplier=0.75,
        confirmed_trade_date="2026-04-20",
        summary_reason="测试信号",
        buy_signal_state="buy_now",
        buy_signal_text="确定买入",
        buy_signal_hint="测试",
        reasons=[],
        risks=[],
        tags=[],
    )


def _backtest_item(
    *,
    net_return_pct: float,
    exit_reason: str,
    max_gain_pct: float,
    max_drawdown_pct: float,
) -> LowBuyExecutionBacktestItemOut:
    return LowBuyExecutionBacktestItemOut(
        symbol="000001",
        name="测试股份",
        strategy_key="first_board",
        signal_trade_date="2026-04-20",
        status="filled",
        net_return_pct=net_return_pct,
        exit_reason=exit_reason,
        max_gain_pct=max_gain_pct,
        max_drawdown_pct=max_drawdown_pct,
    )


def _seed_scan(db, candidate: LowBuyCandidateOut) -> None:
    db.add(
        LowBuyScanSnapshot(
            latest_trade_date="2026-04-20",
            strategy_key="classic_retrace",
            strategy_title="原始低吸法",
            strategy_subtitle="",
            strategy_logic="",
            as_of_date="2026-04-20 15:00:00",
            filters_json=f'{{"_result_version": {LOW_BUY_RESULT_VERSION}}}',
        )
    )
    db.add(
        LowBuyResultSnapshot(
            latest_trade_date="2026-04-20",
            strategy_key="classic_retrace",
            symbol=candidate.symbol,
            name=candidate.name,
            score=candidate.score,
            buy_signal_state="buy_now",
            payload_json=candidate.model_dump_json(),
        )
    )
    db.commit()


def _seed_daily_rows(db, symbol: str) -> None:
    rows = [
        ("2026-04-20", 10.0, 10.0, 10.2, 9.9, 0.0),
        ("2026-04-21", 10.0, 10.5, 10.75, 9.95, 5.0),
        ("2026-04-22", 10.55, 10.8, 10.9, 10.4, 2.8),
    ]
    for trade_date, open_price, close_price, high_price, low_price, pct_chg in rows:
        db.add(
            DailyBarSnapshot(
                symbol=symbol,
                trade_date=trade_date,
                open_price=open_price,
                close_price=close_price,
                high_price=high_price,
                low_price=low_price,
                pct_chg=pct_chg,
                volume=1_000_000,
                amount=100_000_000,
            )
        )
    db.commit()


def _lifecycle_values(entry_high: float, name: str = "测试股份") -> dict:
    return {
        "signal_trade_date": "2026-04-20",
        "strategy_key": "classic_retrace",
        "symbol": "000001",
        "name": name,
        "signal_state": "buy_now",
        "status": "planned",
        "entry_plan_low": 9.8,
        "entry_plan_high": entry_high,
        "stop_loss": 9.4,
        "take_profit": 10.7,
        "max_holding_days": 5,
        "payload_json": "{}",
    }


if __name__ == "__main__":
    unittest.main()
