from __future__ import annotations

import hashlib
import json
import threading
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.entities import LowBuyResultSnapshot, LowBuyScanSnapshot
from app.models.schemas import (
    LowBuyCandidateOut,
    LowBuyHistorySectionOut,
    LowBuyPortfolioRiskOut,
    LowBuyScreenerResponse,
    LowBuyStrategyPerformanceOut,
)
from app.services.low_buy.candidate import LowBuyCandidateMixin
from app.services.low_buy.history import LowBuyHistoryMixin
from app.services.low_buy.mobile import LowBuyMobileReadMixin
from app.services.low_buy.performance import LowBuyPerformanceMixin
from app.services.low_buy.pool import LowBuyPoolMixin
from app.services.low_buy.priority_board import LowBuyPriorityBoardMixin
from app.services.low_buy.priority_snapshot import build_priority_base_snapshot
from app.services.low_buy.priority_types import PriorityBaseSnapshot, PriorityCandidate, StrategyHit
from app.services.low_buy.results import LowBuyResultStoreMixin
from app.services.low_buy.screening_read import screen_read_path
from app.services.low_buy.shared import (
    LOW_BUY_PERFORMANCE_SNAPSHOT_VERSION,
    LOW_BUY_RESULT_VERSION,
    normalize_low_buy_strategy,
)
from backend.tests.support.export_time import export_window_date


EXPECTED_UNPUBLISHED_TRADE_DATE = export_window_date(-3).isoformat()
INTERMEDIATE_TRADE_DATE = export_window_date(-7).isoformat()
STALE_MATERIALIZED_TRADE_DATE = export_window_date(-10).isoformat()


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


def _priority_candidates(count: int) -> list[PriorityCandidate]:
    rows: list[PriorityCandidate] = []
    for index in range(1, count + 1):
        symbol = f"{index:06d}"
        candidate = _candidate(
            symbol=symbol,
            name=f"测试{index}",
            strategy_key="first_board",
            strategy_title="首板回调",
            score=70.0 + index,
            latest_price=10.0 + index / 10,
            entry_zone_low=9.8 + index / 10,
            entry_zone_high=10.1 + index / 10,
            stop_loss=9.5 + index / 10,
            sector_name="银行" if index % 2 else "证券",
            buy_signal_state="soft_buy_now",
            recommendation_days=index % 4 + 1,
            recommendation_start_date="2026-04-22",
        )
        rows.append(
            PriorityCandidate(
                symbol=symbol,
                hits=[
                    StrategyHit(
                        strategy_key="first_board",
                        strategy_title="首板回调",
                        family_key="front_row",
                        candidate=candidate,
                        strategy_weight_score=80.0,
                        context_bonus=0.0,
                        performance=_performance(),
                    )
                ],
            )
        )
    return rows


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


class _PrioritySnapshotQueryBudgetService(_PrioritySnapshotTargetService):
    def __init__(self) -> None:
        self.loaded: list[tuple[str, str]] = []

    @staticmethod
    def _resolve_priority_target_trade_date() -> str:
        return "2026-04-25"

    def _load_materialized_full_result(self, db, strategy: str, latest_trade_date: str, limit: int, include_history: bool):  # noqa: ARG002
        self.loaded.append((strategy, latest_trade_date))
        return None


class _PriorityBoardMarketDataStub:
    @staticmethod
    def get_quotes_batch(symbols, **_kwargs):  # noqa: ANN001
        return {symbol: type("_Quote", (), {"last_price": 0.0})() for symbol in symbols}

    @staticmethod
    def get_intraday_bars_batch(**_kwargs):  # noqa: ANN001
        return {}


class _PriorityBoardHotReadService(LowBuyPriorityBoardMixin):
    def __init__(self, rows: list[PriorityCandidate]) -> None:
        self.rows = rows
        self.market_data = _PriorityBoardMarketDataStub()
        self._priority_base_cache = {}
        self._priority_response_cache = {}
        self._priority_base_cache_ttl = 120.0
        self._priority_response_cache_ttl = 30.0

    @staticmethod
    def _resolve_latest_completed_trade_date(trade_dates: list[str]) -> str:
        return trade_dates[-1] if trade_dates else ""

    @staticmethod
    def _load_cached_strategy_performance(*_args, **_kwargs):  # noqa: ANN001
        return _performance()

    @staticmethod
    def _load_strategy_performance_snapshot(*_args, **_kwargs):  # noqa: ANN001
        return _performance()

    @staticmethod
    def _build_strategy_performance_snapshot(*_args, **_kwargs):  # noqa: ANN001
        return _performance()

    @staticmethod
    def _ensure_recent_strategy_performance_snapshot(*_args, **_kwargs):  # noqa: ANN001
        return _performance()

    @staticmethod
    def _get_priority_response_cache(*_args, **_kwargs):  # noqa: ANN001
        return None

    @staticmethod
    def _set_priority_response_cache(*_args, **_kwargs):  # noqa: ANN001
        return None

    @staticmethod
    def _get_priority_read_model(*_args, **_kwargs):  # noqa: ANN001
        return None

    @staticmethod
    def _set_priority_read_model(*_args, **_kwargs):  # noqa: ANN001
        return None

    def _load_priority_base_snapshot(self, db, limit: int):  # noqa: ARG002
        return PriorityBaseSnapshot(
            latest_trade_date="2026-04-25",
            latest_available_trade_date="2026-04-25",
            updated_at="2026-04-25 15:00:00",
            candidates=self.rows,
            market_context=self._market_context(),
            expected_trade_date="2026-04-25",
        )

    @staticmethod
    def _refresh_priority_candidates(rows: list[PriorityCandidate]) -> list[PriorityCandidate]:
        return rows

    @staticmethod
    def _attach_priority_recommendation_durations(*, db, rows, latest_trade_date):  # noqa: ANN001, ARG004
        return rows

    @staticmethod
    def _primary_candidates_for_portfolio(*_args, **_kwargs):  # noqa: ANN001
        return []

    @staticmethod
    def _build_market_context(db, latest_trade_date: str):  # noqa: ANN001, ARG004
        return _PriorityBoardHotReadService._market_context()

    @staticmethod
    def _market_context():
        from app.services.low_buy.priority_types import PriorityMarketContext

        return PriorityMarketContext(
            market_state="repair",
            market_bonus=0.0,
            market_state_strength=0.0,
            regime_confidence=0.0,
            state_persistence_days=1,
            transition_risk=0.0,
            market_state_label="repair",
            market_state_description="修复",
            breadth_ready=True,
            emotion_ready=True,
            stock_up_ratio=0.55,
            stock_median_change=0.0,
            style_divergence=0.0,
            hot_turnover=0.0,
            hot_overlap_ratio=0.0,
            limit_down_count=0,
            limit_up_count=0,
            board_height=0,
            previous_board_height=0,
            promotion_ratio=0.0,
            broken_board_ratio=0.0,
            promotion_break_gap=0.0,
            promotion_break_pressure=0.0,
            high_flyer_retreat_ratio=0.0,
            high_flyer_gap_speed=0.0,
            distribution_pressure=0.0,
            emotion_temperature="neutral",
            emotion_temperature_text="中性",
            emotion_temperature_score=0.0,
            hot_industries=[],
            hot_industry_source="historical_cache",
            hot_industry_source_text="测试",
            mainline_lifecycle_state="repair",
            mainline_lifecycle_text="主线阶段：测试",
            industry_ranks={},
        )


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


class _ScreenReadFallbackService:
    def __init__(self, fallback_payload: LowBuyScreenerResponse) -> None:
        self.fallback_payload = fallback_payload
        self.loaded_cached_dates: list[str] = []
        self.loaded_fallback_dates: list[str] = []

    @staticmethod
    def _get_recent_trade_dates(count: int) -> list[str]:  # noqa: ARG004
        return [STALE_MATERIALIZED_TRADE_DATE, INTERMEDIATE_TRADE_DATE, EXPECTED_UNPUBLISHED_TRADE_DATE]

    def _load_cached_full_result(self, db, strategy: str, latest_trade_date: str, limit: int, include_history: bool):  # noqa: ARG002
        self.loaded_cached_dates.append(latest_trade_date)
        return None

    def _load_latest_materialized_full_result_on_or_before(
        self,
        db,
        strategy: str,
        latest_trade_date: str,
        limit: int,
        include_history: bool,
    ):  # noqa: ARG002
        self.loaded_fallback_dates.append(latest_trade_date)
        return self.fallback_payload.model_copy(deep=True)

    @staticmethod
    def _is_full_scan_running(strategy: str, latest_trade_date: str, limit: int, include_history: bool) -> bool:  # noqa: ARG004
        return False

    @staticmethod
    def _attach_strategy_performance(db, payload: LowBuyScreenerResponse, build_if_missing: bool):  # noqa: ARG002
        return payload

    @staticmethod
    def _attach_close_review_snapshot(db, payload: LowBuyScreenerResponse, review_trade_date: str, build_if_missing: bool):  # noqa: ARG002
        return payload

    @staticmethod
    def _load_strategy_performance_snapshot(db, strategy: str, latest_trade_date: str):  # noqa: ARG002
        return None

    @staticmethod
    def _empty_strategy_performance(target_profit_pct: float, lookback_days: int, note: str):  # noqa: ARG002
        return _performance()

    @staticmethod
    def _load_stock_profit_target_pct(db) -> float:  # noqa: ARG002
        return 3.0

    @staticmethod
    def _get_playbook(strategy: str):  # noqa: ARG002
        return None

    @staticmethod
    def _resolve_full_scan_limit(scan_limit: int) -> int:
        return scan_limit


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

    def test_priority_snapshot_latest_available_includes_target_trade_date(self) -> None:
        with self.Session() as db:
            snapshot = build_priority_base_snapshot(
                builder=_PrioritySnapshotTargetService(),
                db=db,
                limit=12,
            )

        self.assertEqual(snapshot.latest_available_trade_date, "2026-04-30")

    def test_priority_snapshot_batches_strategy_summary_reads(self) -> None:
        service = _PrioritySnapshotQueryBudgetService()
        statements: list[str] = []

        with self.Session() as db:
            bind = db.get_bind()

            @event.listens_for(bind, "before_cursor_execute")
            def _count_sql(_conn, _cursor, statement, _parameters, _context, _executemany):  # noqa: ANN001
                if "low_buy_scan_snapshots" in statement or "strategy_tier_overrides" in statement:
                    statements.append(statement)

            try:
                snapshot = build_priority_base_snapshot(builder=service, db=db, limit=12)
            finally:
                event.remove(bind, "before_cursor_execute", _count_sql)

        self.assertEqual(snapshot.latest_trade_date, "")
        self.assertEqual(service.loaded, [])
        self.assertLessEqual(len(statements), 3)

    def test_priority_board_hot_read_query_budget_does_not_scale_with_candidates(self) -> None:
        small_count, small_response = self._measure_priority_board_hot_read(candidate_count=5)
        large_count, large_response = self._measure_priority_board_hot_read(candidate_count=20)

        self.assertEqual([item.symbol for item in large_response.items[:3]], ["000020", "000019", "000018"])
        self.assertLessEqual(large_count, small_count + 2)
        self.assertLessEqual(large_count, 6)
        self.assertEqual(large_response.total_candidates, 20)
        self.assertTrue(all(item.strategy_engine_shadow["shadow_only"] for item in large_response.items))
        self.assertTrue(all(item.strategy_engine_shadow["replacement_enabled"] is False for item in large_response.items))
        self.assertTrue(all(item.production_sort_replaced is False for item in large_response.items))

    def test_priority_board_hot_read_golden_output_keeps_order_and_strategy_guards(self) -> None:
        _query_count, response = self._measure_priority_board_hot_read(candidate_count=20)
        golden = [
            {
                "symbol": item.symbol,
                "strategy_key": item.strategy_key,
                "buy_signal_state": item.buy_signal_state,
                "priority_score": item.priority_score,
                "production_score": item.production_score,
                "display_lane": item.display_lane,
                "production_sort_replaced": item.production_sort_replaced,
                "shadow_only": item.strategy_engine_shadow["shadow_only"],
                "replacement_enabled": item.strategy_engine_shadow["replacement_enabled"],
            }
            for item in response.items[:5]
        ]
        digest = hashlib.sha256(json.dumps(golden, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

        self.assertEqual(digest, "5d981f6e5ddaa9289c20fddc2ee1a0ed98442655421f002415947d7696f3ac1d")

    def _measure_priority_board_hot_read(self, *, candidate_count: int):
        service = _PriorityBoardHotReadService(_priority_candidates(candidate_count))
        statements: list[str] = []

        with self.Session() as db:
            bind = db.get_bind()

            @event.listens_for(bind, "before_cursor_execute")
            def _count_sql(_conn, _cursor, statement, _parameters, _context, _executemany):  # noqa: ANN001
                tracked_tables = (
                    "low_buy_scan_snapshots",
                    "low_buy_result_snapshots",
                    "low_buy_strategy_performance_snapshots",
                    "low_buy_trade_lifecycle_snapshots",
                    "strategy_tier_overrides",
                    "watchlist",
                    "system_settings",
                )
                if any(table in statement for table in tracked_tables):
                    statements.append(statement)

            try:
                with patch(
                    "app.services.low_buy.priority_board.enrich_priority_candidates_with_leader_strength",
                    lambda *, db, rows: rows,
                ):
                    response = service.priority_board(db=db, limit=candidate_count, refresh_mode="sync")
            finally:
                event.remove(bind, "before_cursor_execute", _count_sql)

        return len(statements), response

    def test_screen_read_path_returns_stale_materialized_snapshot_when_latest_unpublished(self) -> None:
        fallback = _payload(_candidate(strategy_key="first_board", strategy_title="首板回调")).model_copy(
            update={
                "strategy_key": "first_board",
                "strategy_title": "首板回调",
                "latest_trade_date": STALE_MATERIALIZED_TRADE_DATE,
                "requested_mode": "full",
                "response_mode": "full",
                "full_scan_ready": True,
                "full_scan_in_progress": False,
            }
        )
        service = _ScreenReadFallbackService(fallback)

        with patch("app.services.low_buy.screening_read.expected_low_buy_trade_date", lambda _db: EXPECTED_UNPUBLISHED_TRADE_DATE), \
                patch("app.services.low_buy.screening_read.published_low_buy_trade_date", lambda _db: ""):
            with self.Session() as db:
                response = screen_read_path(
                    service,
                    db,
                    strategy="first_board",
                    limit=16,
                    include_history=False,
                    scan_mode="quick",
                )

        self.assertEqual(service.loaded_cached_dates, [EXPECTED_UNPUBLISHED_TRADE_DATE])
        self.assertEqual(service.loaded_fallback_dates, [EXPECTED_UNPUBLISHED_TRADE_DATE])
        self.assertEqual(response.latest_trade_date, STALE_MATERIALIZED_TRADE_DATE)
        self.assertTrue(response.stale)
        self.assertIn(STALE_MATERIALIZED_TRADE_DATE, response.stale_reason)
        self.assertIn(EXPECTED_UNPUBLISHED_TRADE_DATE, response.stale_reason)
        self.assertIn("仅供复盘", response.snapshot_warning)

    def test_load_latest_materialized_full_result_on_or_before_ignores_newer_incomplete_date(self) -> None:
        service = _RepairingResultService(repaired_payload=_payload(_candidate()))
        with self.Session() as db:
            for trade_date in ("2026-04-28", "2026-05-06"):
                db.add(
                    LowBuyScanSnapshot(
                        latest_trade_date=trade_date,
                        strategy_key="classic_retrace",
                        strategy_title="原始低吸法",
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
                candidate = _candidate().model_copy(
                    update={"symbol": "000001" if trade_date == "2026-04-28" else "000002"}
                )
                db.add(
                    LowBuyResultSnapshot(
                        latest_trade_date=trade_date,
                        strategy_key="classic_retrace",
                        symbol=candidate.symbol,
                        name=candidate.name,
                        score=candidate.score,
                        buy_signal_state=candidate.buy_signal_state,
                        payload_json=candidate.model_dump_json(),
                    )
                )
            db.commit()

            payload = service._load_latest_materialized_full_result_on_or_before(
                db=db,
                strategy="classic_retrace",
                latest_trade_date="2026-04-28",
                limit=16,
                include_history=False,
            )

        self.assertIsNotNone(payload)
        self.assertEqual(payload.latest_trade_date, "2026-04-28")

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
