from __future__ import annotations

import threading
import unittest

from app.models.schemas import (
    KlineBar,
    LowBuyCandidateOut,
    LowBuyStrategyPerformanceOut,
    MicrostructureSnapshot,
    QuoteSnapshot,
    SectorSnapshot,
)
from app.services.distribution_signals import DistributionSnapshot
from app.services.low_buy.candidate_types import CandidateMetrics
from app.services.low_buy.candidate_rules import passes_strategy_prefilter
from app.services.low_buy.dynamic_adjustments import apply_performance_adjustment_to_candidate
from app.services.low_buy.hard_risk import hard_untradable_reason
from app.services.low_buy.industry_positioning import build_industry_position_adjustment
from app.services.low_buy.risk_tiers import resolve_low_buy_risk_tier
from app.services.low_buy.signal_resolution import intraday_soft_confirmation
from app.services.low_buy.screening_quotes import LowBuyQuoteRefreshMixin
from app.services.low_buy.shared import BoardCandidate
from app.services.low_buy.candidate import LowBuyCandidateMixin
from app.services.quant_engine_execution import negative_buyback_allowed, negative_direction_gate, positive_direction_gate
from app.services.quant_engine_models import IndicatorSnapshot
from app.services.quant_engine_scenes import resolve_trade_scene
from app.services.low_buy.signals import LowBuySignalMixin


class _QuoteRefreshService(LowBuyQuoteRefreshMixin, LowBuySignalMixin, LowBuyCandidateMixin):
    pass


def _metrics(**overrides) -> CandidateMetrics:
    data = {
        "latest_trade_date": "2026-04-24",
        "retracement_days": 3,
        "latest_open": 10.0,
        "latest_close": 9.8,
        "latest_high": 10.2,
        "latest_low": 9.6,
        "latest_change_pct": -1.2,
        "ma5": 9.9,
        "ma10": 9.7,
        "ma20": 9.4,
        "ma60": 8.8,
        "board_open": 9.5,
        "board_close": 10.1,
        "board_low": 9.4,
        "board_high": 10.1,
        "board_mid_price": 9.75,
        "board_gain_ok": True,
        "volume_burst_ratio": 2.1,
        "latest_volume_ratio": 0.72,
        "post_volume_ratio": 0.62,
        "shrink_staircase": True,
        "close_to_ma5": 1.0,
        "close_to_ma10": 1.0,
        "close_to_ma20": 2.0,
        "support_distance_pct": 1.2,
        "support_distance_ma20_pct": 2.0,
        "breakout_level": 9.5,
        "breakout_distance_pct": 1.4,
        "platform_high": 9.5,
        "platform_low": 8.8,
        "platform_window_days": 24,
        "platform_range_pct": 18.0,
        "platform_breakout_pct": 1.8,
        "platform_support_distance_pct": 1.2,
        "divergence_high": 10.25,
        "divergence_volume_ratio": 0.82,
        "divergence_day_stall": True,
        "consolidation_days": 3,
        "consolidation_low": 9.55,
        "consolidation_high": 10.18,
        "consolidation_volume_ratio": 0.58,
        "consensus_breakout": False,
        "consensus_volume_ratio": 1.2,
        "consensus_close_strength": 0.62,
        "recent_low_guard": 9.35,
        "recent_swing_high": 10.5,
        "drawdown_from_board_pct": -4.5,
        "latest_body_pct": 0.8,
        "upper_shadow_ratio": 0.12,
        "lower_shadow_ratio": 0.34,
        "close_position_ratio": 0.52,
        "doji_like": True,
        "long_lower_shadow": True,
        "long_upper_shadow": False,
        "weak_close": False,
        "false_breakout_flag": False,
        "stall_after_volume_flag": False,
        "intraday_reversal_flag": False,
        "distribution_risk_score": 2.0,
        "momentum_exhaustion": True,
        "trend_ok": True,
        "strong_trend": True,
        "support_ok": True,
        "shrink_ok": True,
        "shrink_basic_ok": True,
        "board_low_held": True,
        "board_open_held": True,
        "support_watch_ok": True,
        "latest_change_ok": True,
    }
    data.update(overrides)
    return CandidateMetrics(**data)


def _candidate() -> LowBuyCandidateOut:
    return LowBuyCandidateOut(
        strategy_key="classic_retrace",
        strategy_title="原始低吸法",
        symbol="000001",
        name="平安银行",
        market="SZ",
        instrument_type="stock",
        sector_name="银行",
        latest_price=10.0,
        change_pct=1.0,
        quote_timestamp="2026-04-24 10:00:00",
        board_date="2026-04-20",
        board_count=1,
        retracement_days=3,
        score=90.0,
        entry_zone_low=9.8,
        entry_zone_high=10.1,
        stop_loss=9.5,
        take_profit=11.0,
        ma5=9.9,
        ma10=9.7,
        ma20=9.4,
        volume_burst_ratio=2.0,
        volume_shrink_ratio=0.62,
        support_distance_pct=1.2,
        execution_ready=True,
        execution_note="测试",
        suggested_position_pct=20.0,
        suggested_position_text="测试",
        summary_reason="测试",
        buy_signal_state="buy_now",
        buy_signal_text="确定买入",
        buy_signal_hint="测试",
        reasons=["测试"],
        risks=["测试"],
        tags=["测试"],
    )


def _board_candidate(**overrides) -> BoardCandidate:
    data = {
        "symbol": "000001",
        "name": "平安银行",
        "board_date": "2026-04-20",
        "board_count": 1,
        "amount": 220_000_000.0,
        "industry": "银行",
    }
    data.update(overrides)
    return BoardCandidate(**data)

class StrategySafetyLayerTests(unittest.TestCase):
    def test_strict_false_breakout_risk_blocks_low_buy(self) -> None:
        decision = resolve_low_buy_risk_tier(
            strategy="limit_up_breakout_retrace",
            metrics=_metrics(false_breakout_flag=True, distribution_risk_score=4.2),
            market_regime=None,
        )

        self.assertEqual(decision.risk_tier, "block")
        self.assertTrue(decision.execution_blocked)

    def test_poor_performance_requires_enough_filled_samples_before_position_adjustment(self) -> None:
        candidate = _candidate()
        small_sample = LowBuyStrategyPerformanceOut(
            evaluated_signals=16,
            filled_signals=4,
            hit_rate=32.0,
            net_win_rate=-36.0,
            avg_return_5d=-3.2,
            avg_net_return_pct=-3.2,
            avg_max_drawdown_5d=-7.0,
        )
        larger_sample = small_sample.model_copy(update={"evaluated_signals": 80, "filled_signals": 60})

        unchanged = apply_performance_adjustment_to_candidate(candidate, small_sample)
        adjusted = apply_performance_adjustment_to_candidate(candidate, larger_sample)

        self.assertEqual(unchanged.dynamic_position_multiplier, candidate.dynamic_position_multiplier)
        self.assertLess(adjusted.dynamic_position_multiplier, candidate.dynamic_position_multiplier)

    def test_core_strategy_requires_minimum_liquidity(self) -> None:
        self.assertFalse(
            passes_strategy_prefilter(
                strategy="volume_shrink",
                item=_board_candidate(amount=30_000_000),
                metrics=_metrics(),
            )
        )

    def test_low_buy_untradable_reason_blocks_limit_locked_candidates(self) -> None:
        reason, tag = hard_untradable_reason(
            item=_board_candidate(),
            metrics=_metrics(latest_change_pct=10.0, close_position_ratio=0.96),
        )

        self.assertIn("涨停", reason)
        self.assertEqual(tag, "硬风控:涨停追高")

    def test_low_buy_untradable_reason_blocks_suspected_suspension(self) -> None:
        reason, tag = hard_untradable_reason(
            item=_board_candidate(amount=0),
            metrics=_metrics(),
        )

        self.assertIn("疑似停牌", reason)
        self.assertEqual(tag, "硬风控:疑似停牌")

    def test_deep_pullback_factor_caps_non_core_position(self) -> None:
        candidate = _candidate().model_copy(
            update={
                "strategy_key": "ma_support",
                "buy_signal_state": "buy_now",
                "factor_scores": {"deep_pullback_factor": 5.0},
            }
        )

        position_pct, text = LowBuyCandidateMixin._position_advice_for_signal(candidate, "buy_now")

        self.assertLessEqual(position_pct, 10.0)
        self.assertIn("仓位封顶", text)

    def test_industry_positioning_boosts_core_hot_and_cuts_cold_sector(self) -> None:
        core = build_industry_position_adjustment(
            sector_name="人工智能",
            hot_industries=["人工智能", "机器人"],
            leader_rank="leader",
            market_state="repair",
            market_state_strength=0.5,
        )
        cold = build_industry_position_adjustment(
            sector_name="银行",
            hot_industries=["人工智能", "机器人"],
            leader_rank="laggard",
            market_state="high_flyer_retreat",
            market_state_strength=0.8,
        )

        self.assertEqual(core.tier, "core_hot")
        self.assertGreater(core.multiplier, 1.0)
        self.assertEqual(cold.tier, "cold")
        self.assertLess(cold.multiplier, 0.82)

    def test_distribution_scene_disallows_positive_t(self) -> None:
        scene = resolve_trade_scene(
            quote=_quote(),
            indicators=_indicators(distribution_risk_score=7.8),
            sector=SectorSnapshot(sector_name="人工智能", sector_strength=50, market_strength=48, alignment_score=50, notes=""),
            microstructure=MicrostructureSnapshot(available=True, buy_pressure=45, sell_pressure=58),
            market_regime=None,
        )

        self.assertEqual(scene.key, "distribution_defense")
        self.assertNotIn("positive_t", scene.allowed_actions)

    def test_negative_t_requires_valid_buyback_anchor(self) -> None:
        allowed, reason = negative_buyback_allowed(buy_price=10.2, vwap_value=0.0, ma5=10.0)

        self.assertFalse(allowed)
        self.assertIn("参考位", reason)

    def test_positive_t_requires_pullback_acceptance_structure(self) -> None:
        allowed, reason = positive_direction_gate(
            quote=_quote(),
            ma5=10.0,
            ma20=9.8,
            slope10=0.1,
            vwap_value=10.05,
            sector=SectorSnapshot(sector_name="人工智能", sector_strength=60, market_strength=55, alignment_score=62, notes=""),
            microstructure=MicrostructureSnapshot(available=True, buy_pressure=62, sell_pressure=42),
            distribution=_distribution(distribution_risk_score=1.0),
            intraday_structure="balanced_intraday",
        )

        self.assertFalse(allowed)
        self.assertIn("回落后有人接盘", reason)

    def test_negative_t_requires_buyback_room(self) -> None:
        quote = _quote().model_copy(update={"last_price": 10.04, "high_price": 10.08, "low_price": 9.95})
        allowed, reason = negative_direction_gate(
            quote=quote,
            ma5=10.0,
            rsi14=70.0,
            macd_hist=-0.03,
            vwap_value=10.0,
            amplitude=3.0,
            sector=SectorSnapshot(sector_name="人工智能", sector_strength=55, market_strength=52, alignment_score=55, notes=""),
            microstructure=MicrostructureSnapshot(available=True, buy_pressure=42, sell_pressure=62),
            distribution=_distribution(distribution_risk_score=5.0, stall_after_volume_flag=True),
            intraday_structure="volume_stall",
        )

        self.assertFalse(allowed)
        self.assertIn("接回空间不足", reason)

    def test_weak_market_blocks_non_mainline_thematic_low_buy(self) -> None:
        candidate = _candidate().model_copy(
            update={
                "instrument_type": "stock",
                "market_state": "fast_rotation",
                "leader_rank": "laggard",
                "industry_tier": "neutral",
            }
        )

        reason = LowBuySignalMixin._weak_market_thematic_block_reason(candidate)

        self.assertIn("只保留主线龙头", reason)

    def test_intraday_confirmation_requires_minute_reclaim_when_bars_exist(self) -> None:
        quote = _quote().model_copy(update={"last_price": 10.0, "open_price": 9.95, "low_price": 9.82, "high_price": 10.05})
        weak_bars = [
            _bar("2026-04-24 09:31", 10.02, 9.95, 10.04, 9.94, 1200),
            _bar("2026-04-24 09:32", 9.95, 9.91, 9.96, 9.90, 1100),
            _bar("2026-04-24 09:33", 9.91, 9.89, 9.93, 9.88, 900),
        ]
        reclaim_bars = [
            _bar("2026-04-24 09:31", 9.9, 9.88, 9.93, 9.86, 900),
            _bar("2026-04-24 09:32", 9.88, 9.94, 9.95, 9.87, 850),
            _bar("2026-04-24 09:33", 9.94, 10.01, 10.02, 9.92, 1100),
        ]

        self.assertFalse(intraday_soft_confirmation(_candidate(), quote, intraday_bars=weak_bars, vwap_value=10.1))
        self.assertTrue(intraday_soft_confirmation(_candidate(), quote, intraday_bars=reclaim_bars, vwap_value=9.96))

    def test_quote_refresh_caps_minute_bar_fanout(self) -> None:
        service = _QuoteRefreshService()
        symbols = [f"000{i:03d}" for i in range(30)]
        materialized = {
            symbol: _candidate().model_copy(
                update={
                    "symbol": symbol,
                    "buy_signal_state": "near_entry",
                    "entry_zone_low": 9.8,
                    "entry_zone_high": 10.1,
                    "latest_price": 10.0,
                }
            )
            for symbol in symbols
        }
        quote_map = {
            symbol: _quote().model_copy(update={"symbol": symbol, "last_price": 10.0})
            for symbol in symbols
        }

        selected = service._select_intraday_refresh_symbols(
            symbols=symbols,
            materialized=materialized,
            quote_map=quote_map,
            max_symbols=24,
        )

        self.assertEqual(len(selected), 24)

    def test_quote_refresh_normalizes_and_caps_symbols(self) -> None:
        symbols = [" 000001 ", "000001", "", "sz000002", *[f"600{i:03d}" for i in range(30)]]

        normalized = _QuoteRefreshService._normalize_quote_refresh_symbols(symbols)

        self.assertEqual(normalized[0], "000001")
        self.assertEqual(normalized[1], "SZ000002")
        self.assertEqual(len(normalized), 32)
        self.assertEqual(len(set(normalized)), len(normalized))

    def test_quote_refresh_degrades_when_quote_source_fails(self) -> None:
        class FailingMarketData:
            def get_quotes_batch(self, *_args, **_kwargs):
                raise RuntimeError("quote source unavailable")

        service = _QuoteRefreshService()
        service.market_data = FailingMarketData()
        service._cache_lock = threading.Lock()
        service._quote_refresh_response_cache = {}
        service._quote_refresh_response_cache_ttl = 1.0

        payload = service._build_quote_refresh_payloads(["000001"], {})

        self.assertEqual(payload, {})

    def test_stale_quote_never_upgrades_low_buy_signal(self) -> None:
        service = _QuoteRefreshService()
        candidate = _candidate().model_copy(
            update={
                "strategy_key": "first_board",
                "score": 96.0,
                "execution_ready": True,
            }
        )
        stale_quote = _quote().model_copy(
            update={
                "last_price": 9.95,
                "is_stale": True,
                "timestamp": "2026-04-24 09:45:00",
            }
        )

        refreshed = service._refresh_buy_signal(candidate, quote=stale_quote)

        self.assertEqual(refreshed.buy_signal_state, "watch")
        self.assertIn("行情时间已过期", refreshed.buy_signal_hint)


def _quote() -> QuoteSnapshot:
    return QuoteSnapshot(
        symbol="000001",
        name="平安银行",
        market="SZ",
        instrument_type="stock",
        last_price=10.2,
        change_pct=2.1,
        change_amount=0.2,
        open_price=10.0,
        high_price=10.5,
        low_price=9.9,
        prev_close=10.0,
        volume=1_000_000,
        amount=300_000_000,
        timestamp="2026-04-24 10:00:00",
    )


def _bar(timestamp: str, open_price: float, close_price: float, high_price: float, low_price: float, volume: float) -> KlineBar:
    return KlineBar(
        timestamp=timestamp,
        open=open_price,
        close=close_price,
        high=high_price,
        low=low_price,
        volume=volume,
        amount=volume * close_price,
    )


def _distribution(**overrides) -> DistributionSnapshot:
    data = {
        "upper_shadow_ratio": 0.1,
        "close_position_ratio": 0.65,
        "weak_close": False,
        "long_upper_shadow": False,
        "false_breakout_flag": False,
        "stall_after_volume_flag": False,
        "intraday_reversal_flag": False,
        "distribution_risk_score": 1.0,
    }
    data.update(overrides)
    return DistributionSnapshot(**data)


def _indicators(distribution_risk_score: float) -> IndicatorSnapshot:
    return IndicatorSnapshot(
        ma5=10.0,
        ma20=9.8,
        ma60=9.2,
        rsi14=68.0,
        macd_dif=0.1,
        macd_dea=0.08,
        macd_hist=-0.02,
        macd_valid=True,
        vwap_value=10.05,
        atr14=0.18,
        volume_ratio_value=1.4,
        amplitude=3.2,
        slope10=0.1,
        obv_value=1_000_000,
        distribution=DistributionSnapshot(
            upper_shadow_ratio=0.4,
            close_position_ratio=0.3,
            weak_close=True,
            long_upper_shadow=True,
            false_breakout_flag=False,
            stall_after_volume_flag=False,
            intraday_reversal_flag=True,
            distribution_risk_score=distribution_risk_score,
        ),
        latest_bar=None,
    )


if __name__ == "__main__":
    unittest.main()
