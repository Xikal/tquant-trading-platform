from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pandas as pd

from app.models.schemas import LowBuyCandidateOut, MicrostructureSnapshot, QuoteSnapshot, SectorSnapshot
from app.services.distribution_signals import DistributionSnapshot
from app.services.low_buy.signals import LowBuySignalMixin
from app.services.market.emotion import MarketEmotionMixin
from app.services.market.regime import MarketRegimeMixin, MarketRegimeSnapshot
from app.services.quant_engine_execution import negative_direction_gate, positive_direction_gate


def _market_regime(state: str, strength: float = 0.4) -> MarketRegimeSnapshot:
    return MarketRegimeSnapshot(
        state=state,
        label=state,
        description=state,
        ranking_bonus=0.0,
        position_multiplier=0.8,
        buy_signal_penalty=1.0,
        t_threshold_shift=0.1,
        positive_threshold_shift=1.0,
        negative_threshold_shift=1.0,
        hot_industries=[],
        hot_industry_source="",
        hot_industry_source_text="",
        limit_down_count=10,
        breadth_ready=True,
        emotion_ready=True,
        positive_industry_ratio=0.4,
        top3_avg_change=1.0,
        median_change=0.1,
        defensive_lead=False,
        stock_up_ratio=0.42,
        stock_median_change=-0.1,
        largecap_change=0.4,
        smallcap_change=-0.4,
        style_divergence=0.8,
        hot_turnover=0.4,
        hot_overlap_ratio=0.2,
        limit_up_count=20,
        previous_limit_up_count=26,
        board_height=3,
        previous_board_height=4,
        promotion_ratio=0.28,
        broken_board_ratio=0.22,
        promotion_break_gap=0.06,
        promotion_break_pressure=0.44,
        high_flyer_retreat_ratio=0.18,
        high_flyer_gap_speed=0.33,
        distribution_pressure=0.22,
        mainline_lifecycle_state="stable",
        mainline_lifecycle_text="主线阶段：持续沉淀",
        state_strength=strength,
        regime_score=56.0,
    )


def _distribution(
    *,
    false_breakout: bool = False,
    stall_after_volume: bool = False,
    intraday_reversal: bool = False,
    risk_score: float = 0.0,
) -> DistributionSnapshot:
    return DistributionSnapshot(
        upper_shadow_ratio=0.42 if intraday_reversal else 0.12,
        close_position_ratio=0.24 if intraday_reversal else 0.62,
        weak_close=intraday_reversal or false_breakout,
        long_upper_shadow=intraday_reversal,
        false_breakout_flag=false_breakout,
        stall_after_volume_flag=stall_after_volume,
        intraday_reversal_flag=intraday_reversal,
        distribution_risk_score=risk_score,
    )


def _candidate() -> LowBuyCandidateOut:
    return LowBuyCandidateOut(
        strategy_key="classic_retrace",
        strategy_title="原始低吸法",
        symbol="000001",
        name="平安银行",
        market="SZ",
        instrument_type="stock",
        sector_name="银行",
        latest_price=10.05,
        change_pct=-0.6,
        quote_timestamp="2026-04-24 10:05:00",
        board_date="2026-04-22",
        board_count=1,
        retracement_days=3,
        score=90.0,
        entry_zone_low=9.8,
        entry_zone_high=10.0,
        stop_loss=9.55,
        take_profit=10.8,
        ma5=9.95,
        ma10=9.7,
        ma20=9.4,
        volume_burst_ratio=2.1,
        volume_shrink_ratio=0.62,
        support_distance_pct=1.2,
        execution_ready=True,
        execution_note="结构成熟",
        entry_distance_pct=0.5,
        suggested_position_pct=20.0,
        suggested_position_text="先试仓",
        market_state="weight_support",
        market_state_text="权重护盘",
        market_state_strength=0.4,
        market_position_multiplier=0.82,
        confirmed_trade_date=None,
        summary_reason="回踩承接",
        buy_signal_state="watch",
        buy_signal_text="继续观察",
        buy_signal_hint="等待确认",
        reasons=["测试"],
        risks=["测试"],
        tags=["测试"],
    )


class _SignalHarness(LowBuySignalMixin):
    @staticmethod
    def _position_advice_for_signal(candidate, state):  # noqa: ARG004
        return 20.0, state


class _EmotionHarness(MarketEmotionMixin):
    pass


class SimpleProviderRouter:
    def __init__(self, *, circuit_open: bool) -> None:
        self.circuit_open = circuit_open

    def all_providers_circuit_open(self, operation: str) -> bool:
        assert operation == "fetch_board_breadth_frame"
        return self.circuit_open


class _RegimeFallbackHarness(MarketRegimeMixin):
    def __init__(self, persisted: MarketRegimeSnapshot | None, *, circuit_open: bool = False) -> None:
        self.persisted = persisted
        self.provider_router = SimpleProviderRouter(circuit_open=circuit_open)
        self.persisted_calls = 0
        self.emotion_calls = 0
        self.board_calls = 0
        self.persisted_snapshots: list[MarketRegimeSnapshot] = []
        self.cache: dict[str, MarketRegimeSnapshot] = {}

    @staticmethod
    def _resolve_regime_trade_date(_latest_trade_date):  # noqa: ANN001
        return "2026-06-12"

    def _load_board_breadth_frame(self):
        self.board_calls += 1
        return None

    @staticmethod
    def _resolve_hot_industries(_board_frame, hot_industries):
        return hot_industries or []

    @staticmethod
    def _load_market_breadth_snapshot(_recent_hot_sequences=None):  # noqa: ANN001
        raise AssertionError("persisted fallback should avoid live breadth fallback work")

    def _load_market_emotion_snapshot(self, _latest_trade_date):  # noqa: ANN001
        self.emotion_calls += 1
        raise AssertionError("persisted fallback should avoid provider-backed emotion work")

    @staticmethod
    def _load_limit_down_count_cached(_latest_trade_date):  # noqa: ANN001
        raise AssertionError("persisted fallback should avoid provider-backed limit-down work")

    @staticmethod
    def _stabilize_market_regime(snapshot, _previous_snapshot):  # noqa: ANN001
        return snapshot

    @staticmethod
    def _apply_market_readiness_guard(snapshot):
        return snapshot

    @staticmethod
    def _apply_regime_continuity(snapshot, _previous_snapshot):  # noqa: ANN001
        return snapshot

    def _get_compatible_regime_cache(self, cache_key, _hot_industries):  # noqa: ANN001
        return self.cache.get(cache_key)

    def _set_market_regime_cache(self, cache_key, snapshot):  # noqa: ANN001
        self.cache[cache_key] = snapshot

    @staticmethod
    def _peek_market_regime_snapshot(_cache_key):  # noqa: ANN001
        return None

    def _load_persisted_market_regime_snapshot(self, cache_key, _hot_industries):  # noqa: ANN001
        assert cache_key == "2026-06-12"
        self.persisted_calls += 1
        return self.persisted

    def _persist_market_regime_snapshot(self, _cache_key, snapshot):  # noqa: ANN001
        self.persisted_snapshots.append(snapshot)


class MarketRegimeStrategyP2Tests(unittest.TestCase):
    def setUp(self) -> None:
        MarketRegimeMixin._clear_provider_degraded("fetch_board_breadth_frame")
        MarketRegimeMixin._exit_provider_probe("fetch_board_breadth_frame")

    def tearDown(self) -> None:
        MarketRegimeMixin._clear_provider_degraded("fetch_board_breadth_frame")
        MarketRegimeMixin._exit_provider_probe("fetch_board_breadth_frame")

    def test_provider_degraded_cooldown_uses_runtime_setting(self) -> None:
        with (
            patch(
                "app.services.market.regime.get_settings",
                return_value=SimpleNamespace(
                    market_regime_provider_degraded_cooldown_seconds=300.0,
                ),
            ),
            patch("app.services.market.regime.time.monotonic", return_value=1000.0),
        ):
            MarketRegimeMixin._remember_provider_degraded("fetch_board_breadth_frame")

        self.assertEqual(
            MarketRegimeMixin._provider_degraded_until["fetch_board_breadth_frame"],
            1300.0,
        )

    def test_provider_degraded_cooldown_falls_back_for_invalid_setting(self) -> None:
        with patch(
            "app.services.market.regime.get_settings",
            return_value=SimpleNamespace(
                market_regime_provider_degraded_cooldown_seconds="invalid",
            ),
        ):
            self.assertEqual(
                MarketRegimeMixin._provider_degraded_cooldown_seconds(),
                MarketRegimeMixin._provider_degraded_default_cooldown_seconds,
            )

    def test_hot_overlap_uses_ranked_yesterday_today_continuity(self) -> None:
        stable = MarketRegimeMixin._compute_hot_overlap_ratio(
            [["人工智能", "机器人", "算力"], ["人工智能", "机器人", "传媒"]]
        )
        rotating = MarketRegimeMixin._compute_hot_overlap_ratio(
            [["人工智能", "机器人", "算力"], ["银行", "保险", "煤炭"]]
        )

        self.assertGreater(stable, 0.5)
        self.assertLess(rotating, 0.1)

    def test_market_emotion_snapshot_builds_time_series_metrics(self) -> None:
        current_pool = pd.DataFrame({"连板数": [1, 2, 2]})
        broken_pool = pd.DataFrame({"代码": ["a", "b"]})
        previous_board_pool = pd.DataFrame(
            {
                "昨日连板数": [1, 2, 3, 4],
                "涨跌幅": [1.0, -1.0, -2.0, -6.0],
            }
        )
        previous_limit_up_pool = pd.DataFrame({"连板数": [1, 2, 4, 3]})

        snapshot = _EmotionHarness._build_market_emotion_snapshot(
            current_pool=current_pool,
            broken_pool=broken_pool,
            previous_board_pool=previous_board_pool,
            previous_limit_up_pool=previous_limit_up_pool,
        )

        self.assertEqual(snapshot.previous_board_height, 4)
        self.assertGreater(snapshot.promotion_break_gap, 0.0)
        self.assertGreater(snapshot.high_flyer_gap_speed, 0.7)
        self.assertGreater(snapshot.emotion_distribution_pressure, 0.0)

    def test_market_regime_uses_persisted_snapshot_when_live_provider_unavailable(self) -> None:
        persisted = replace(
            _market_regime("repair"),
            snapshot_source="cached",
            snapshot_source_text="使用 2026-06-12 最近完整市场快照，后台正在刷新实时情绪",
        )
        harness = _RegimeFallbackHarness(persisted)

        snapshot = harness.get_market_regime(hot_industries=["半导体"])

        self.assertIs(snapshot, persisted)
        self.assertEqual(snapshot.snapshot_source, "cached")
        self.assertEqual(harness.persisted_calls, 1)
        self.assertEqual(harness.emotion_calls, 0)
        self.assertEqual(harness.persisted_snapshots, [])
        self.assertIs(harness.cache["2026-06-12"], persisted)

    def test_market_regime_uses_short_degraded_cooldown_after_provider_failure(self) -> None:
        persisted = replace(
            _market_regime("repair"),
            snapshot_source="cached",
            snapshot_source_text="使用 2026-06-12 最近完整市场快照，后台正在刷新实时情绪",
        )
        first = _RegimeFallbackHarness(persisted)

        self.assertIs(first.get_market_regime(hot_industries=["半导体"]), persisted)
        self.assertEqual(first.board_calls, 1)
        self.assertEqual(first.persisted_calls, 1)

        second = _RegimeFallbackHarness(persisted)
        self.assertIs(second.get_market_regime(hot_industries=["半导体"]), persisted)
        self.assertEqual(second.board_calls, 0)
        self.assertEqual(second.persisted_calls, 1)

    def test_market_regime_skips_live_provider_when_breadth_circuit_open(self) -> None:
        persisted = replace(
            _market_regime("repair"),
            snapshot_source="cached",
            snapshot_source_text="使用 2026-06-12 最近完整市场快照，后台正在刷新实时情绪",
        )
        harness = _RegimeFallbackHarness(persisted, circuit_open=True)

        snapshot = harness.get_market_regime(hot_industries=["半导体"])

        self.assertIs(snapshot, persisted)
        self.assertEqual(harness.board_calls, 0)
        self.assertEqual(harness.persisted_calls, 1)

    def test_market_regime_returns_lightweight_snapshot_when_circuit_open_without_persisted_snapshot(self) -> None:
        harness = _RegimeFallbackHarness(None, circuit_open=True)

        snapshot = harness.get_market_regime(hot_industries=["半导体"])

        self.assertEqual(snapshot.snapshot_source, "warming")
        self.assertEqual(snapshot.hot_industries, ["半导体"])
        self.assertEqual(snapshot.hot_industry_source, "cached_fallback")
        self.assertEqual(harness.board_calls, 0)
        self.assertEqual(harness.persisted_calls, 1)
        self.assertEqual(harness.persisted_snapshots, [])

    def test_market_regime_returns_lightweight_snapshot_after_live_provider_failure_without_persisted_snapshot(self) -> None:
        harness = _RegimeFallbackHarness(None)

        snapshot = harness.get_market_regime(hot_industries=["半导体"])

        self.assertEqual(snapshot.snapshot_source, "warming")
        self.assertEqual(snapshot.hot_industries, ["半导体"])
        self.assertEqual(snapshot.hot_industry_source, "cached_fallback")
        self.assertEqual(harness.board_calls, 1)
        self.assertEqual(harness.persisted_calls, 1)
        self.assertEqual(harness.emotion_calls, 0)
        self.assertEqual(harness.persisted_snapshots, [])

    def test_market_regime_skips_second_live_probe_while_board_probe_is_inflight(self) -> None:
        persisted = replace(
            _market_regime("repair"),
            snapshot_source="cached",
            snapshot_source_text="使用 2026-06-12 最近完整市场快照，后台正在刷新实时情绪",
        )
        self.assertTrue(MarketRegimeMixin._try_enter_provider_probe("fetch_board_breadth_frame"))
        harness = _RegimeFallbackHarness(persisted)

        snapshot = harness.get_market_regime(hot_industries=["半导体"])

        self.assertIs(snapshot, persisted)
        self.assertEqual(harness.board_calls, 0)
        self.assertEqual(harness.persisted_calls, 1)

    def test_market_block_happens_in_signal_layer(self) -> None:
        harness = _SignalHarness()
        candidate = _candidate().model_copy(
            update={
                "strategy_key": "limit_up_breakout_retrace",
                "market_state": "fast_rotation",
                "market_state_text": "轮动过快",
                "market_state_strength": 0.7,
                "score": 94.0,
            }
        )

        updated = harness._resolve_signal_state(
            candidate=candidate,
            entry_position="in_zone",
            entry_distance=0.0,
            hard_confirmed=True,
            soft_confirmed=True,
            historical=False,
        )

        self.assertEqual(updated.buy_signal_state, "near_entry")
        self.assertIn("承接", updated.buy_signal_hint)

    def test_restricted_market_keeps_high_quality_candidate_on_watchlist(self) -> None:
        harness = _SignalHarness()
        candidate = _candidate().model_copy(
            update={
                "strategy_key": "ma_support",
                "market_state": "high_flyer_retreat",
                "market_state_text": "高位退潮",
                "market_state_strength": 0.76,
                "score": 94.0,
                "distribution_risk_score": 2.0,
                "leader_rank": "strong_follow",
                "industry_tier": "core_hot",
            }
        )

        updated = harness._resolve_signal_state(
            candidate=candidate,
            entry_position="near_above_zone",
            entry_distance=0.45,
            hard_confirmed=False,
            soft_confirmed=True,
            historical=False,
        )

        self.assertEqual(updated.buy_signal_state, "near_entry")
        self.assertEqual(updated.buy_signal_text, "接近买点")

    def test_restricted_market_rejects_weak_or_risky_candidates(self) -> None:
        harness = _SignalHarness()
        base_candidate = _candidate().model_copy(
            update={
                "strategy_key": "ma_support",
                "market_state": "high_flyer_retreat",
                "market_state_text": "高位退潮",
                "market_state_strength": 0.76,
                "leader_rank": "strong_follow",
            }
        )

        cases = [
            (
                base_candidate.model_copy(update={"score": 86.0, "distribution_risk_score": 2.0}),
                "near_above_zone",
                0.45,
            ),
            (
                base_candidate.model_copy(update={"score": 94.0, "distribution_risk_score": 6.0}),
                "near_above_zone",
                0.45,
            ),
            (
                base_candidate.model_copy(update={"score": 94.0, "distribution_risk_score": 2.0}),
                "below_zone",
                1.2,
            ),
        ]

        for candidate, entry_position, entry_distance in cases:
            with self.subTest(entry_position=entry_position, entry_distance=entry_distance, score=candidate.score):
                updated = harness._resolve_signal_state(
                    candidate=candidate,
                    entry_position=entry_position,
                    entry_distance=entry_distance,
                    hard_confirmed=False,
                    soft_confirmed=False,
                    historical=False,
                )

                self.assertEqual(updated.buy_signal_state, "avoid")

    def test_paused_observation_strategy_near_above_stays_near_entry(self) -> None:
        harness = _SignalHarness()
        candidate = _candidate().model_copy(
            update={
                "strategy_key": "limit_up_breakout_retrace",
                "research_stage": "near_entry",
            }
        )

        updated = harness._resolve_signal_state(
            candidate=candidate,
            entry_position="near_above_zone",
            entry_distance=0.5,
            hard_confirmed=False,
            soft_confirmed=True,
            historical=False,
        )

        self.assertEqual(updated.buy_signal_state, "near_entry")

    def test_structure_false_breakout_blocks_only_when_risk_is_high(self) -> None:
        weak_false_breakout = _candidate().model_copy(
            update={"false_breakout_flag": True, "distribution_risk_score": 5.8}
        )
        severe_false_breakout = _candidate().model_copy(
            update={"false_breakout_flag": True, "distribution_risk_score": 7.1}
        )

        self.assertFalse(_SignalHarness._has_distribution_hard_block(weak_false_breakout))
        self.assertTrue(_SignalHarness._has_distribution_hard_block(severe_false_breakout))

    def test_strict_false_breakout_still_blocks_execution(self) -> None:
        strict_candidate = _candidate().model_copy(
            update={
                "strategy_key": "limit_up_breakout_retrace",
                "false_breakout_flag": True,
                "distribution_risk_score": 4.2,
            }
        )

        self.assertTrue(_SignalHarness._has_distribution_hard_block(strict_candidate))

    def test_positive_direction_gate_distinguishes_weight_and_thematic_stock(self) -> None:
        quote = QuoteSnapshot(
            symbol="600000",
            name="浦发银行",
            market="SH",
            instrument_type="stock",
            last_price=10.18,
            change_pct=1.2,
            change_amount=0.12,
            open_price=10.04,
            high_price=10.22,
            low_price=9.98,
            prev_close=10.06,
            volume=1000000,
            amount=500000000,
            timestamp="2026-04-24 10:08:00",
        )
        micro = MicrostructureSnapshot(available=True, buy_pressure=43.0, sell_pressure=48.0)
        regime = _market_regime("weight_support", 0.52)

        allowed_weight, _ = positive_direction_gate(
            quote=quote,
            ma5=10.0,
            ma20=9.92,
            slope10=-0.22,
            vwap_value=10.10,
            sector=SectorSnapshot(sector_name="银行", sector_strength=55.0, market_strength=48.0, alignment_score=34.0, notes=""),
            microstructure=micro,
            distribution=_distribution(),
            market_regime=regime,
            intraday_structure="pullback_acceptance",
        )
        allowed_theme, _ = positive_direction_gate(
            quote=quote.model_copy(update={"name": "题材股"}),
            ma5=10.0,
            ma20=9.92,
            slope10=-0.22,
            vwap_value=10.10,
            sector=SectorSnapshot(sector_name="人工智能", sector_strength=55.0, market_strength=48.0, alignment_score=34.0, notes=""),
            microstructure=micro,
            distribution=_distribution(),
            market_regime=regime,
            intraday_structure="pullback_acceptance",
        )

        self.assertTrue(allowed_weight)
        self.assertFalse(allowed_theme)

    def test_negative_direction_gate_distinguishes_weight_and_thematic_stock(self) -> None:
        quote = QuoteSnapshot(
            symbol="600011",
            name="华能国际",
            market="SH",
            instrument_type="stock",
            last_price=9.98,
            change_pct=1.1,
            change_amount=0.11,
            open_price=9.85,
            high_price=10.06,
            low_price=9.84,
            prev_close=9.87,
            volume=1000000,
            amount=300000000,
            timestamp="2026-04-24 14:18:00",
        )
        micro = MicrostructureSnapshot(available=True, buy_pressure=49.0, sell_pressure=46.0)
        regime = _market_regime("weight_support_active", 0.55)

        allowed_weight, _ = negative_direction_gate(
            quote=quote,
            ma5=9.9,
            rsi14=61.0,
            macd_hist=-0.03,
            vwap_value=9.92,
            amplitude=1.82,
            sector=SectorSnapshot(sector_name="电力", sector_strength=48.0, market_strength=46.0, alignment_score=40.0, notes=""),
            microstructure=micro,
            distribution=_distribution(),
            market_regime=regime,
            intraday_structure="overheat_exhaustion",
        )
        allowed_theme, _ = negative_direction_gate(
            quote=quote.model_copy(update={"name": "题材股"}),
            ma5=9.9,
            rsi14=61.0,
            macd_hist=-0.03,
            vwap_value=9.92,
            amplitude=1.82,
            sector=SectorSnapshot(sector_name="机器人", sector_strength=48.0, market_strength=46.0, alignment_score=40.0, notes=""),
            microstructure=micro,
            distribution=_distribution(),
            market_regime=regime,
            intraday_structure="overheat_exhaustion",
        )

        self.assertTrue(allowed_weight)
        self.assertFalse(allowed_theme)

    def test_positive_direction_gate_blocks_false_breakout_even_for_weight_stock(self) -> None:
        quote = QuoteSnapshot(
            symbol="600000",
            name="浦发银行",
            market="SH",
            instrument_type="stock",
            last_price=10.18,
            change_pct=1.2,
            change_amount=0.12,
            open_price=10.04,
            high_price=10.28,
            low_price=9.98,
            prev_close=10.06,
            volume=1000000,
            amount=500000000,
            timestamp="2026-04-24 10:18:00",
        )

        allowed, reason = positive_direction_gate(
            quote=quote,
            ma5=10.0,
            ma20=9.92,
            slope10=-0.12,
            vwap_value=10.12,
            sector=SectorSnapshot(sector_name="银行", sector_strength=55.0, market_strength=48.0, alignment_score=40.0, notes=""),
            microstructure=MicrostructureSnapshot(available=True, buy_pressure=48.0, sell_pressure=46.0),
            distribution=_distribution(false_breakout=True, risk_score=7.8),
            market_regime=_market_regime("weight_support_active", 0.55),
        )

        self.assertFalse(allowed)
        self.assertIn("假突破", reason)

    def test_positive_direction_gate_blocks_stall_after_volume_in_fast_rotation(self) -> None:
        quote = QuoteSnapshot(
            symbol="002000",
            name="题材股",
            market="SZ",
            instrument_type="stock",
            last_price=10.26,
            change_pct=1.4,
            change_amount=0.14,
            open_price=10.05,
            high_price=10.34,
            low_price=10.01,
            prev_close=10.12,
            volume=1200000,
            amount=260000000,
            timestamp="2026-04-24 10:28:00",
        )

        allowed, reason = positive_direction_gate(
            quote=quote,
            ma5=10.08,
            ma20=9.94,
            slope10=0.04,
            vwap_value=10.18,
            sector=SectorSnapshot(sector_name="机器人", sector_strength=52.0, market_strength=46.0, alignment_score=49.0, notes=""),
            microstructure=MicrostructureSnapshot(available=True, buy_pressure=54.0, sell_pressure=44.0),
            distribution=_distribution(stall_after_volume=True, risk_score=5.6),
            market_regime=_market_regime("fast_rotation", 0.66),
        )

        self.assertFalse(allowed)
        self.assertIn("放量但价格涨不动", reason)

    def test_negative_direction_gate_relaxes_for_distribution_bias(self) -> None:
        quote = QuoteSnapshot(
            symbol="002000",
            name="题材股",
            market="SZ",
            instrument_type="stock",
            last_price=10.16,
            change_pct=0.7,
            change_amount=0.07,
            open_price=9.96,
            high_price=10.18,
            low_price=9.95,
            prev_close=9.95,
            volume=1000000,
            amount=220000000,
            timestamp="2026-04-24 14:12:00",
        )
        micro = MicrostructureSnapshot(available=True, buy_pressure=46.0, sell_pressure=47.0)
        regime = _market_regime("weight_support_active", 0.58)

        blocked_without_distribution, _ = negative_direction_gate(
            quote=quote,
            ma5=10.04,
            rsi14=59.0,
            macd_hist=-0.01,
            vwap_value=10.03,
            amplitude=1.75,
            sector=SectorSnapshot(sector_name="机器人", sector_strength=48.0, market_strength=46.0, alignment_score=42.0, notes=""),
            microstructure=micro,
            distribution=_distribution(),
            market_regime=regime,
        )
        allowed_with_distribution, _ = negative_direction_gate(
            quote=quote,
            ma5=10.04,
            rsi14=59.0,
            macd_hist=-0.01,
            vwap_value=10.03,
            amplitude=1.75,
            sector=SectorSnapshot(sector_name="机器人", sector_strength=48.0, market_strength=46.0, alignment_score=42.0, notes=""),
            microstructure=micro,
            distribution=_distribution(false_breakout=True, stall_after_volume=True, intraday_reversal=True, risk_score=6.0),
            market_regime=regime,
            intraday_structure="false_breakout",
        )

        self.assertFalse(blocked_without_distribution)
        self.assertTrue(allowed_with_distribution)

    def test_negative_direction_gate_allows_lower_etf_amplitude_in_risk_state(self) -> None:
        quote = QuoteSnapshot(
            symbol="510300",
            name="沪深300ETF",
            market="SH",
            instrument_type="etf",
            last_price=4.08,
            change_pct=0.9,
            change_amount=0.04,
            open_price=4.03,
            high_price=4.11,
            low_price=4.02,
            prev_close=4.04,
            volume=1000000,
            amount=900000000,
            timestamp="2026-04-24 14:22:00",
        )

        allowed, _ = negative_direction_gate(
            quote=quote,
            ma5=4.03,
            rsi14=63.0,
            macd_hist=-0.02,
            vwap_value=4.04,
            amplitude=1.82,
            sector=SectorSnapshot(sector_name="宽基ETF", sector_strength=50.0, market_strength=46.0, alignment_score=38.0, notes=""),
            microstructure=MicrostructureSnapshot(available=True, buy_pressure=48.0, sell_pressure=48.0),
            distribution=_distribution(),
            market_regime=_market_regime("risk_release", 0.62),
            intraday_structure="overheat_exhaustion",
        )

        self.assertTrue(allowed)


if __name__ == "__main__":
    unittest.main()
