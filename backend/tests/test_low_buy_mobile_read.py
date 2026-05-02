from __future__ import annotations

import threading
import time
import unittest

from app.models.schemas import LowBuyCandidateOut, LowBuyScreenerResponse, LowBuyStrategyPerformanceOut
from app.services.low_buy.candidate import LowBuyCandidateMixin
from app.services.low_buy.mobile import LowBuyMobileReadMixin
from app.services.low_buy.performance import LowBuyPerformanceMixin
from app.services.low_buy.screening import LowBuyScreeningMixin
from app.services.low_buy.shared import LOW_BUY_PERFORMANCE_SNAPSHOT_VERSION, LOW_BUY_RESULT_VERSION


def _candidate(symbol: str) -> LowBuyCandidateOut:
    return LowBuyCandidateOut(
        strategy_key="classic_retrace",
        strategy_title="原始低吸法",
        payload_version=LOW_BUY_RESULT_VERSION,
        symbol=symbol,
        name=f"候选{symbol}",
        market="SZ",
        instrument_type="stock",
        sector_name="新能源",
        latest_price=18.8,
        change_pct=-1.2,
        quote_timestamp="2026-04-22 10:05:00",
        board_date="2026-04-20",
        board_count=1,
        retracement_days=2,
        score=81.2,
        entry_zone_low=18.5,
        entry_zone_high=18.9,
        stop_loss=17.9,
        take_profit=19.8,
        ma5=18.7,
        ma10=18.1,
        ma20=17.6,
        volume_burst_ratio=1.8,
        volume_shrink_ratio=0.7,
        support_distance_pct=1.1,
        execution_ready=True,
        execution_note="接近入场区，可观察承接",
        entry_distance_pct=0.2,
        suggested_position_pct=20.0,
        suggested_position_text="先试 2 成",
        confirmed_trade_date=None,
        summary_reason="回撤后接近入场区",
        buy_signal_state="near_entry",
        buy_signal_text="接近买点",
        buy_signal_hint="等待承接确认",
        reasons=["测试理由"],
        risks=["测试风险"],
        tags=["测试标签"],
    )


def _payload(*, symbol: str | None = None, response_mode: str = "quick") -> LowBuyScreenerResponse:
    candidates = [_candidate(symbol)] if symbol else []
    return LowBuyScreenerResponse(
        strategy_key="classic_retrace",
        strategy_title="原始低吸法",
        strategy_subtitle="测试副标题",
        strategy_logic="测试逻辑",
        requested_mode=response_mode,
        response_mode=response_mode,
        as_of_date="2026-04-22 10:05:00",
        latest_trade_date="2026-04-22",
        pool_size=120,
        scanned_count=48,
        matched_count=len(candidates),
        requested_scan_limit=48,
        active_scan_limit=48,
        full_scan_ready=response_mode == "full",
        full_scan_in_progress=False,
        full_scan_updated_at="2026-04-22 10:05:00" if response_mode == "full" else None,
        retracement_distribution={"2天": 1},
        filters={"scan_mode": response_mode},
        strategy_notes=["测试说明"],
        performance=LowBuyStrategyPerformanceOut(snapshot_version=LOW_BUY_PERFORMANCE_SNAPSHOT_VERSION),
        close_review_trade_date=None,
        close_review_updated_at=None,
        close_review_items=[],
        confirmed_candidates=[],
        history_sections=[],
        candidates=candidates,
    )


class _MobileReadHarness(
    LowBuyMobileReadMixin,
    LowBuyPerformanceMixin,
    LowBuyCandidateMixin,
    LowBuyScreeningMixin,
):
    def __init__(self) -> None:
        self.market_data = type(
            "_MarketDataStub",
            (),
            {"settings": type("_Settings", (), {"app_mobile_quick_history_timeout": 6.0})()},
        )()
        self._cache_lock = threading.Lock()
        self._screen_cache = {
            "cached:quick": (time.monotonic() + 60.0, _payload(symbol="002594", response_mode="quick"))
        }
        self.snapshot = _payload(symbol=None, response_mode="quick")
        self.mobile_snapshot_calls = 0
        self.expanded_screen_calls = 0

    def mobile_snapshot(
        self,
        db,
        strategy: str = "classic_retrace",
        limit: int = 12,
        fallback_scan_limit: int = 24,
        history_wait_timeout_seconds: float | None = None,
    ):  # noqa: ARG002
        self.mobile_snapshot_calls += 1
        return self.snapshot

    def _load_latest_materialized_candidate_by_symbol(self, db, strategy: str, symbol: str):  # noqa: ARG002
        return None

    def _screen_sync(self, db, strategy: str, limit: int, scan_limit: int, include_history: bool, scan_mode: str, compute_performance: bool, history_wait_timeout_seconds=None):  # noqa: ARG002
        self.expanded_screen_calls += 1
        return _payload(symbol=None, response_mode="quick")

    def _load_strategy_performance_snapshot(self, db, strategy: str, latest_trade_date: str, lookback_days: int = 60):  # noqa: ARG002
        return LowBuyStrategyPerformanceOut(snapshot_version=LOW_BUY_PERFORMANCE_SNAPSHOT_VERSION)

    def _build_strategy_performance_snapshot(self, db, strategy: str, latest_trade_date: str):  # noqa: ARG002
        return LowBuyStrategyPerformanceOut(snapshot_version=LOW_BUY_PERFORMANCE_SNAPSHOT_VERSION)

    def _load_stock_profit_target_pct(self, db):  # noqa: ARG002
        return 3.0


class LowBuyMobileReadTests(unittest.TestCase):
    def test_mobile_candidate_detail_reuses_cached_quick_payload(self) -> None:
        harness = _MobileReadHarness()

        candidate, payload = harness.mobile_candidate_by_symbol(
            db=None,
            symbol="002594",
            strategy="classic_retrace",
            detail_limit=24,
            fallback_scan_limit=48,
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.symbol, "002594")
        self.assertEqual(payload.latest_trade_date, "2026-04-22")
        self.assertEqual(harness.mobile_snapshot_calls, 0)
        self.assertEqual(harness.expanded_screen_calls, 0)


if __name__ == "__main__":
    unittest.main()
