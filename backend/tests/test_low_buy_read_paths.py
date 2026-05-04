from __future__ import annotations

import json
import threading
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.services.low_buy import pool as pool_module
from app.models.base import Base
from app.models.entities import LowBuyResultSnapshot, LowBuyScanSnapshot
from app.models.schemas import (
    LowBuyCandidateOut,
    LowBuyHistorySectionOut,
    LowBuyScreenerResponse,
    LowBuyStrategyPerformanceOut,
)
from app.services.low_buy.candidate import LowBuyCandidateMixin
from app.services.low_buy.history import LowBuyHistoryMixin
from app.services.low_buy.mobile import LowBuyMobileReadMixin
from app.services.low_buy.performance import LowBuyPerformanceMixin
from app.services.low_buy.pool import LowBuyPoolMixin
from app.services.low_buy.priority_snapshot import build_priority_base_snapshot
from app.services.low_buy.results import LowBuyResultStoreMixin
from app.services.low_buy.shared import (
    LOW_BUY_PERFORMANCE_SNAPSHOT_VERSION,
    LOW_BUY_RESULT_VERSION,
    normalize_low_buy_strategy,
)


def _candidate(**overrides) -> LowBuyCandidateOut:
    data = {
        "strategy_key": "classic_retrace",
        "strategy_title": "原始低吸法",
        "payload_version": LOW_BUY_RESULT_VERSION,
        "symbol": "000001",
        "name": "平安银行",
        "market": "SZ",
        "instrument_type": "stock",
        "sector_name": "银行",
        "latest_price": 10.0,
        "change_pct": 1.0,
        "quote_timestamp": "2026-04-25 10:00:00",
        "board_date": "2026-04-20",
        "board_count": 1,
        "retracement_days": 3,
        "score": 88.0,
        "entry_zone_low": 9.8,
        "entry_zone_high": 10.1,
        "stop_loss": 9.5,
        "take_profit": 11.0,
        "ma5": 9.9,
        "ma10": 9.7,
        "ma20": 9.4,
        "volume_burst_ratio": 2.0,
        "volume_shrink_ratio": 0.62,
        "support_distance_pct": 1.2,
        "execution_ready": True,
        "execution_note": "测试",
        "risk_tier": "note",
        "buy_signal_state": "buy_now",
        "buy_signal_text": "确定买入",
        "buy_signal_hint": "测试",
        "market_state": "repair",
        "market_state_text": "修复中",
        "market_position_multiplier": 0.9,
        "risk_position_multiplier": 0.62,
        "industry_tier": "core_hot",
        "industry_tier_text": "核心热点",
        "industry_position_multiplier": 1.08,
        "dynamic_position_multiplier": 1.04,
        "suggested_position_pct": 0.0,
        "suggested_position_text": "",
        "summary_reason": "测试",
        "reasons": ["测试"],
        "risks": ["测试"],
        "tags": ["测试"],
    }
    data.update(overrides)
    return LowBuyCandidateOut(**data)


def _performance() -> LowBuyStrategyPerformanceOut:
    return LowBuyStrategyPerformanceOut(
        snapshot_version=LOW_BUY_PERFORMANCE_SNAPSHOT_VERSION,
        evaluated_signals=80,
        filled_signals=60,
        hit_rate=34.0,
        net_win_rate=-32.0,
        avg_return_5d=-2.6,
        avg_net_return_pct=-2.6,
        avg_max_drawdown_5d=-6.8,
    )


def _payload(candidate: LowBuyCandidateOut) -> LowBuyScreenerResponse:
    return LowBuyScreenerResponse(
        strategy_key="classic_retrace",
        strategy_title="原始低吸法",
        strategy_subtitle="测试",
        strategy_logic="测试",
        requested_mode="quick",
        response_mode="quick",
        as_of_date="2026-04-25 10:00:00",
        latest_trade_date="2026-04-25",
        pool_size=1,
        scanned_count=1,
        matched_count=1,
        requested_scan_limit=24,
        active_scan_limit=24,
        full_scan_ready=False,
        full_scan_in_progress=True,
        full_scan_updated_at=None,
        retracement_distribution={},
        filters={},
        strategy_notes=[],
        confirmed_candidates=[candidate],
        history_sections=[],
        candidates=[],
    )


def _current_filters() -> dict:
    return {
        "_result_version": LOW_BUY_RESULT_VERSION,
        "market_regime": "修复中",
        "market_state": "repair",
        "market_state_strength": 0.4,
        "regime_confidence": 0.8,
        "state_persistence_days": 2,
        "transition_risk": 0.1,
        "breadth_ready": True,
        "emotion_ready": True,
        "market_bonus": 1.2,
        "hot_industries_json": "[]",
        "hot_industry_source": "historical_cache",
        "hot_industry_source_text": "测试",
        "limit_up_count": 12,
        "board_height": 2,
        "promotion_ratio": 0.4,
        "broken_board_ratio": 0.2,
        "high_flyer_retreat_ratio": 0.1,
        "stock_up_ratio": 0.55,
        "stock_median_change": 0.4,
        "style_divergence": 0.2,
        "hot_turnover": 0.8,
        "hot_overlap_ratio": 0.5,
        "previous_board_height": 2,
        "promotion_break_gap": 0.1,
        "promotion_break_pressure": 0.2,
        "high_flyer_gap_speed": 0.1,
        "distribution_pressure": 12.0,
        "mainline_lifecycle_state": "repair",
        "mainline_lifecycle_text": "主线阶段：测试",
        "structure_mode": "完整日线样本",
    }


class _HistoryLoaderService(LowBuyHistoryMixin, LowBuyResultStoreMixin, LowBuyPoolMixin, LowBuyCandidateMixin):
    _full_cache_setting_prefix = "test_low_buy_full_cache"
    _screen_cache = {}
    _daily_history_cache = {}
    _cache_lock = threading.Lock()
    _screen_cache_ttl = 300.0
    _screen_cache_ttl_full = 300.0
    _default_full_scan_limit = 480

    @staticmethod
    def _safe_json_object(raw: str) -> dict:
        try:
            payload = json.loads(raw or "{}")
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}


class _PerformanceService(LowBuyPerformanceMixin, LowBuyCandidateMixin):
    def __init__(self, performance: LowBuyStrategyPerformanceOut | None) -> None:
        self.performance = performance

    def _load_strategy_performance_snapshot(self, db, strategy: str, latest_trade_date: str, lookback_days: int = 60):  # noqa: ARG002
        return self.performance

    def _build_strategy_performance_snapshot(self, db, strategy: str, latest_trade_date: str):  # noqa: ARG002
        return self.performance

    def _load_stock_profit_target_pct(self, db):  # noqa: ARG002
        return 3.0


class _MobileService(LowBuyMobileReadMixin, LowBuyPerformanceMixin, LowBuyCandidateMixin):
    def __init__(self, payload: LowBuyScreenerResponse, performance: LowBuyStrategyPerformanceOut) -> None:
        self.payload = payload
        self.performance = performance
        self.market_data = type(
            "_MarketDataStub",
            (),
            {"settings": type("_SettingsStub", (), {"app_mobile_quick_history_timeout": 6.0})()},
        )()

    def _load_latest_materialized_full_result(self, db, strategy: str, limit: int, include_history: bool):  # noqa: ARG002
        return None

    def _screen_sync(self, db, strategy: str, limit: int, scan_limit: int, include_history: bool, scan_mode: str, compute_performance: bool, history_wait_timeout_seconds: float | None = None):  # noqa: ARG002
        return self.payload.model_copy(deep=True)

    def _load_strategy_performance_snapshot(self, db, strategy: str, latest_trade_date: str, lookback_days: int = 60):  # noqa: ARG002
        return self.performance

    def _build_strategy_performance_snapshot(self, db, strategy: str, latest_trade_date: str):  # noqa: ARG002
        return self.performance

    def _load_stock_profit_target_pct(self, db):  # noqa: ARG002
        return 3.0


class _TradeDateService(LowBuyPoolMixin):
    def __init__(self, latest_artifact_trade_date: str | None) -> None:
        self.latest_artifact_trade_date = latest_artifact_trade_date

    def _load_latest_low_buy_artifact_trade_date(self, trade_dates: list[str]) -> str | None:
        if self.latest_artifact_trade_date in trade_dates:
            return self.latest_artifact_trade_date
        return None

    def _load_daily_history(self, symbol: str, latest_trade_date: str, history_window_days: int = 180):  # noqa: ARG002
        return None


class _PrioritySnapshotTargetService:
    @staticmethod
    def _resolve_priority_target_trade_date() -> str:
        return "2026-04-30"

    @staticmethod
    def _load_watchlist_symbols(db) -> set[str]:  # noqa: ARG002
        return set()

    @staticmethod
    def _load_materialized_full_result(db, strategy: str, latest_trade_date: str, limit: int, include_history: bool):  # noqa: ARG002
        return None

    @staticmethod
    def _collect_priority_candidates(db, merged_candidates, tracked_symbols, latest_trade_date, candidates, performance_cache):  # noqa: ARG002
        return None

    @staticmethod
    def _build_market_context(db, latest_trade_date: str):  # noqa: ARG002
        return None


class _RepairingResultService(LowBuyResultStoreMixin):
    def __init__(self, repaired_payload: LowBuyScreenerResponse) -> None:
        self.repaired_payload = repaired_payload
        self.repair_calls: list[tuple[str, str, int, bool]] = []

    def _rebuild_materialized_snapshot(
        self,
        db,
        strategy: str,
        latest_trade_date: str,
        limit: int,
        include_history: bool,
    ):
        self.repair_calls.append((strategy, latest_trade_date, limit, include_history))
        return self.repaired_payload.model_copy(deep=True)

    @staticmethod
    def _safe_json_object(raw: str) -> dict:
        try:
            payload = json.loads(raw or "{}")
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}


class LowBuyReadPathTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, future=True)
        _HistoryLoaderService._screen_cache = {}

    def test_materialized_confirmed_candidates_skip_stale_payloads(self) -> None:
        service = _HistoryLoaderService()
        stale_payload = _candidate().model_dump()
        stale_payload.pop("risk_tier")

        with self.Session() as db:
            db.add(
                LowBuyScanSnapshot(
                    latest_trade_date="2026-04-25",
                    strategy_key="classic_retrace",
                    strategy_title="原始低吸法",
                    strategy_subtitle="测试",
                    strategy_logic="测试",
                    as_of_date="2026-04-25 15:00:00",
                    pool_size=1,
                    scanned_count=1,
                    matched_count=1,
                    requested_scan_limit=24,
                    active_scan_limit=24,
                    retracement_distribution_json="{}",
                    filters_json=json.dumps(_current_filters(), ensure_ascii=False),
                    strategy_notes_json="[]",
                )
            )
            db.add(
                LowBuyResultSnapshot(
                    latest_trade_date="2026-04-25",
                    strategy_key="classic_retrace",
                    symbol="000001",
                    name="平安银行",
                    score=88.0,
                    buy_signal_state="buy_now",
                    payload_json=json.dumps(stale_payload, ensure_ascii=False),
                )
            )
            db.commit()

            candidates = service._load_materialized_confirmed_candidates(
                latest_trade_date="2026-04-25",
                strategy="classic_retrace",
                max_candidates=8,
                db=db,
            )

        self.assertEqual(candidates, [])

    def test_materialized_scan_is_not_current_when_any_row_is_stale(self) -> None:
        service = _HistoryLoaderService()
        current_payload = json.dumps(_candidate(symbol="000001").model_dump(), ensure_ascii=False)
        stale_payload = _candidate(symbol="000002").model_dump()
        stale_payload.pop("intraday_reversal_flag")

        with self.Session() as db:
            db.add(
                LowBuyScanSnapshot(
                    latest_trade_date="2026-04-25",
                    strategy_key="classic_retrace",
                    strategy_title="原始低吸法",
                    strategy_subtitle="测试",
                    strategy_logic="测试",
                    as_of_date="2026-04-25 15:00:00",
                    pool_size=2,
                    scanned_count=2,
                    matched_count=2,
                    requested_scan_limit=24,
                    active_scan_limit=24,
                    retracement_distribution_json="{}",
                    filters_json=json.dumps(_current_filters(), ensure_ascii=False),
                    strategy_notes_json="[]",
                )
            )
            db.add_all(
                [
                    LowBuyResultSnapshot(
                        latest_trade_date="2026-04-25",
                        strategy_key="classic_retrace",
                        symbol="000001",
                        name="平安银行",
                        score=99.0,
                        buy_signal_state="buy_now",
                        payload_json=current_payload,
                    ),
                    LowBuyResultSnapshot(
                        latest_trade_date="2026-04-25",
                        strategy_key="classic_retrace",
                        symbol="000002",
                        name="万科A",
                        score=88.0,
                        buy_signal_state="buy_now",
                        payload_json=json.dumps(stale_payload, ensure_ascii=False),
                    ),
                ]
            )
            db.commit()

            self.assertFalse(
                service._materialized_scan_is_current(
                    db=db,
                    strategy="classic_retrace",
                    latest_trade_date="2026-04-25",
                )
            )

    def test_candidate_payload_is_not_current_when_new_field_is_invalid(self) -> None:
        service = _HistoryLoaderService()
        invalid_payload = _candidate().model_dump()
        invalid_payload["risk_position_multiplier"] = None

        self.assertFalse(service._candidate_payload_is_current(invalid_payload))

    def test_legacy_full_cache_payload_must_pass_raw_candidate_currentity(self) -> None:
        service = _HistoryLoaderService()
        legacy_payload = _payload(_candidate()).model_dump()
        legacy_payload["filters"] = _current_filters()
        legacy_payload["confirmed_candidates"][0].pop("payload_version")

        self.assertFalse(service._response_payload_is_current(json.dumps(legacy_payload, ensure_ascii=False)))

    def test_cached_full_result_normalizes_policy_and_duration(self) -> None:
        service = _HistoryLoaderService()
        payload = _payload(_candidate(strategy_key="first_board", strategy_title="首板回调"))
        payload = payload.model_copy(
            update={
                "requested_mode": "full",
                "response_mode": "full",
                "full_scan_ready": True,
                "full_scan_in_progress": False,
            }
        )
        cache_key = service._make_screen_cache_key(
            strategy="first_board",
            latest_trade_date="2026-04-25",
            limit=16,
            scan_limit=service._default_full_scan_limit,
            include_history=False,
            scan_mode="full",
        )
        service._set_screen_cache(cache_key, payload)

        with self.Session() as db:
            for trade_date in ["2026-04-25", "2026-04-24"]:
                db.add(
                    LowBuyScanSnapshot(
                        latest_trade_date=trade_date,
                        strategy_key="first_board",
                        strategy_title="首板回调",
                        strategy_subtitle="测试",
                        strategy_logic="测试",
                        as_of_date=f"{trade_date} 15:00:00",
                        pool_size=1,
                        scanned_count=1,
                        matched_count=1,
                        requested_scan_limit=24,
                        active_scan_limit=24,
                        retracement_distribution_json="{}",
                        filters_json=json.dumps(_current_filters(), ensure_ascii=False),
                        strategy_notes_json="[]",
                    )
                )
            db.add(
                LowBuyResultSnapshot(
                    latest_trade_date="2026-04-24",
                    strategy_key="first_board",
                    symbol="000001",
                    name="平安银行",
                    score=88.0,
                    buy_signal_state="near_entry",
                    payload_json=json.dumps(_candidate().model_dump(), ensure_ascii=False),
                )
            )
            db.commit()

            cached = service._load_cached_full_result(
                db=db,
                strategy="first_board",
                latest_trade_date="2026-04-25",
                limit=16,
                include_history=False,
            )

        self.assertIsNotNone(cached)
        candidate = cached.confirmed_candidates[0]  # type: ignore[union-attr]
        self.assertEqual(candidate.buy_signal_state, "buy_now")
        self.assertIn("第 2 天", candidate.recommendation_duration_text)
        self.assertNotIn("连续推荐", candidate.recommendation_duration_text)

    def test_filter_current_performance_rows_skips_stale_payloads(self) -> None:
        service = _PerformanceService(_performance())
        rows = [
            type("_Row", (), {"payload_json": json.dumps(_candidate(symbol="000001").model_dump(), ensure_ascii=False)})(),
            type("_Row", (), {"payload_json": json.dumps({"payload_version": LOW_BUY_RESULT_VERSION}, ensure_ascii=False)})(),
        ]
        service._candidate_payload_is_current = _HistoryLoaderService._candidate_payload_is_current  # type: ignore[attr-defined]

        filtered = service._filter_current_performance_rows(rows)

        self.assertEqual(len(filtered), 1)

    def test_history_sections_apply_same_performance_positioning(self) -> None:
        service = _PerformanceService(_performance())
        sections = [
            LowBuyHistorySectionOut(
                title="历史",
                description="测试",
                candidates=[_candidate(market_position_multiplier=1.0, risk_position_multiplier=1.0, industry_position_multiplier=1.0, dynamic_position_multiplier=1.0)],
            )
        ]

        updated = service._apply_strategy_performance_to_history_sections(sections, _performance())

        self.assertLess(updated[0].candidates[0].suggested_position_pct, 30.0)
        self.assertTrue(updated[0].candidates[0].position_breakdown_text)

    def test_mobile_snapshot_normalizes_fallback_payload(self) -> None:
        service = _MobileService(_payload(_candidate()), _performance())

        snapshot = service.mobile_snapshot(
            db=None,
            strategy="classic_retrace",
            limit=12,
            fallback_scan_limit=24,
        )

        self.assertEqual(snapshot.requested_mode, "quick")
        self.assertTrue(snapshot.full_scan_ready)
        self.assertFalse(snapshot.full_scan_in_progress)
        self.assertEqual(snapshot.full_scan_updated_at, snapshot.as_of_date)

    def test_resolve_latest_completed_trade_date_uses_low_buy_artifact_when_daily_history_lags(self) -> None:
        service = _TradeDateService(latest_artifact_trade_date="2026-04-24")

        self.assertEqual(
            service._resolve_latest_completed_trade_date(["2026-04-22", "2026-04-23", "2026-04-24"]),
            "2026-04-24",
        )

    def test_latest_completed_calendar_fallback_uses_latest_completed_holiday_date(self) -> None:
        service = _TradeDateService(latest_artifact_trade_date=None)
        original_date = pool_module.date

        class _FakeDate:
            @classmethod
            def today(cls):
                return original_date(2026, 5, 4)

        try:
            pool_module.date = _FakeDate
            self.assertEqual(
                service._latest_completed_calendar_fallback(["2026-04-28", "2026-04-29", "2026-04-30"]),
                "2026-04-30",
            )
            self.assertEqual(
                service._latest_completed_calendar_fallback(["2026-04-30", "2026-05-04"]),
                "2026-04-30",
            )
        finally:
            pool_module.date = original_date

    def test_recent_trade_dates_do_not_call_remote_calendar_when_local_store_lags(self) -> None:
        service = _TradeDateService(latest_artifact_trade_date=None)
        service._trade_dates_cache = {}
        original_date = pool_module.date
        remote_called = False

        class _FakeDate:
            @classmethod
            def today(cls):
                return original_date(2026, 5, 4)

        try:
            pool_module.date = _FakeDate
            service._load_recent_trade_dates_from_local_store = lambda count: ["2026-04-28", "2026-04-29"]  # type: ignore[method-assign]

            def _remote_calendar(*, count, today):  # noqa: ANN001
                nonlocal remote_called
                remote_called = True
                return ["2026-04-30"]

            service._load_recent_trade_dates_from_remote = _remote_calendar  # type: ignore[method-assign]

            self.assertEqual(
                service._get_recent_trade_dates(14),
                ["2026-04-28", "2026-04-29"],
            )
            self.assertFalse(remote_called)
        finally:
            pool_module.date = original_date

    def test_recent_trade_dates_append_today_from_local_calendar_for_intraday_mode(self) -> None:
        service = _TradeDateService(latest_artifact_trade_date=None)
        service._trade_dates_cache = {}
        original_date = pool_module.date

        class _FakeDate:
            @classmethod
            def today(cls):
                return original_date(2026, 4, 30)

        try:
            pool_module.date = _FakeDate
            service._load_recent_trade_dates_from_local_store = lambda count: ["2026-04-28", "2026-04-29"]  # type: ignore[method-assign]
            service._load_recent_trade_dates_from_remote = lambda *, count, today: (_ for _ in ()).throw(  # type: ignore[method-assign]
                AssertionError("remote calendar must not be called from read path")
            )

            self.assertEqual(
                service._get_recent_trade_dates(14),
                ["2026-04-28", "2026-04-29", "2026-04-30"],
            )
        finally:
            pool_module.date = original_date

    def test_priority_snapshot_latest_available_includes_target_trade_date(self) -> None:
        with self.Session() as db:
            snapshot = build_priority_base_snapshot(
                builder=_PrioritySnapshotTargetService(),
                db=db,
                limit=12,
            )

        self.assertEqual(snapshot.latest_available_trade_date, "2026-04-30")

    def test_load_latest_materialized_full_result_skips_invalid_latest_snapshot_before_fallback(self) -> None:
        repaired_payload = _payload(_candidate()).model_copy(update={"latest_trade_date": "2026-04-25"})
        service = _RepairingResultService(repaired_payload=repaired_payload)
        stale_payload = _candidate().model_dump()
        stale_payload.pop("dynamic_position_multiplier")

        with self.Session() as db:
            db.add(
                LowBuyScanSnapshot(
                    latest_trade_date="2026-04-25",
                    strategy_key="classic_retrace",
                    strategy_title="原始低吸法",
                    strategy_subtitle="测试",
                    strategy_logic="测试",
                    as_of_date="2026-04-25 15:00:00",
                    pool_size=1,
                    scanned_count=1,
                    matched_count=1,
                    requested_scan_limit=24,
                    active_scan_limit=24,
                    retracement_distribution_json="{}",
                    filters_json=json.dumps(_current_filters(), ensure_ascii=False),
                    strategy_notes_json="[]",
                )
            )
            db.add(
                LowBuyResultSnapshot(
                    latest_trade_date="2026-04-25",
                    strategy_key="classic_retrace",
                    symbol="000001",
                    name="平安银行",
                    score=88.0,
                    buy_signal_state="buy_now",
                    payload_json=json.dumps(stale_payload, ensure_ascii=False),
                )
            )
            db.add(
                LowBuyScanSnapshot(
                    latest_trade_date="2026-04-24",
                    strategy_key="classic_retrace",
                    strategy_title="原始低吸法",
                    strategy_subtitle="测试",
                    strategy_logic="测试",
                    as_of_date="2026-04-24 15:00:00",
                    pool_size=1,
                    scanned_count=1,
                    matched_count=1,
                    requested_scan_limit=24,
                    active_scan_limit=24,
                    retracement_distribution_json="{}",
                    filters_json=json.dumps(_current_filters(), ensure_ascii=False),
                    strategy_notes_json="[]",
                )
            )
            db.commit()

            payload = service._load_latest_materialized_full_result(
                db=db,
                strategy="classic_retrace",
                limit=16,
                include_history=False,
            )

        self.assertIsNotNone(payload)
        self.assertEqual(payload.latest_trade_date, "2026-04-24")
        self.assertEqual(service.repair_calls, [])

    def test_load_latest_materialized_full_result_can_skip_sync_repair(self) -> None:
        repaired_payload = _payload(_candidate()).model_copy(update={"latest_trade_date": "2026-04-25"})
        service = _RepairingResultService(repaired_payload=repaired_payload)
        stale_payload = _candidate().model_dump()
        stale_payload.pop("dynamic_position_multiplier")

        with self.Session() as db:
            db.add(
                LowBuyScanSnapshot(
                    latest_trade_date="2026-04-25",
                    strategy_key="classic_retrace",
                    strategy_title="原始低吸法",
                    strategy_subtitle="测试",
                    strategy_logic="测试",
                    as_of_date="2026-04-25 15:00:00",
                    pool_size=1,
                    scanned_count=1,
                    matched_count=1,
                    requested_scan_limit=24,
                    active_scan_limit=24,
                    retracement_distribution_json="{}",
                    filters_json=json.dumps(_current_filters(), ensure_ascii=False),
                    strategy_notes_json="[]",
                )
            )
            db.add(
                LowBuyResultSnapshot(
                    latest_trade_date="2026-04-25",
                    strategy_key="classic_retrace",
                    symbol="000001",
                    name="平安银行",
                    score=88.0,
                    buy_signal_state="buy_now",
                    payload_json=json.dumps(stale_payload, ensure_ascii=False),
                )
            )
            db.commit()

            payload = service._load_latest_materialized_full_result(
                db=db,
                strategy="classic_retrace",
                limit=16,
                include_history=False,
                allow_repair=False,
            )

        self.assertIsNone(payload)
        self.assertEqual(service.repair_calls, [])

    def test_legacy_strategy_keys_are_normalized(self) -> None:
        self.assertEqual(normalize_low_buy_strategy("volume_pullback"), "volume_shrink")
        self.assertEqual(normalize_low_buy_strategy("position_support"), "breakout_support")
        self.assertEqual(normalize_low_buy_strategy("dragon_head_retrace"), "trend_rebound")


if __name__ == "__main__":
    unittest.main()
