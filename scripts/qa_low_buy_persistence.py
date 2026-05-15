from datetime import datetime
from pathlib import Path
import sys

import pandas as pd
from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal, init_db
from app.models.entities import (
    DailyBarSnapshot,
    LowBuyCloseReviewSnapshot,
    LowBuyPoolSnapshot,
    LowBuyResultSnapshot,
    LowBuyScanSnapshot,
    LowBuyStrategyPerformanceSnapshot,
    LowBuyStrategyPerformanceWindowSnapshot,
)
from app.models.schemas import LowBuyCloseReviewItemOut, LowBuyScreenerResponse
from app.services.low_buy_screener import (
    LOW_BUY_RESULT_VERSION,
    BoardCandidate,
    LowBuyScreenerService,
)


def _fake_history() -> pd.DataFrame:
    trade_dates = pd.bdate_range("2026-01-05", "2026-04-17")
    return pd.DataFrame(
        {
            "date": trade_dates.strftime("%Y-%m-%d"),
            "open": [10 + index * 0.02 for index in range(len(trade_dates))],
            "close": [10.1 + index * 0.02 for index in range(len(trade_dates))],
            "high": [10.2 + index * 0.02 for index in range(len(trade_dates))],
            "low": [9.9 + index * 0.02 for index in range(len(trade_dates))],
            "volume": [1_000_000 + index * 1_000 for index in range(len(trade_dates))],
            "amount": [20_000_000 + index * 20_000 for index in range(len(trade_dates))],
            "pct_chg": [0.2 for _ in range(len(trade_dates))],
        }
    )


class FakeDailyHistoryResult:
    usable = True
    data = _fake_history()


def _install_fake_history(service: LowBuyScreenerService) -> None:
    fake_history = _fake_history()

    def fake_call_akshare(func, *args, **kwargs):
        if getattr(func, "__name__", "") == "stock_zh_a_daily":
            return fake_history.copy()
        raise RuntimeError(f"unexpected akshare call: {getattr(func, '__name__', repr(func))}")

    service.market_data._call_akshare = fake_call_akshare
    service.market_data._to_sina_symbol = lambda symbol: f"sz{symbol}" if symbol.startswith(("0", "3")) else f"sh{symbol}"
    service.market_data.provider_router.fetch_daily_history = lambda symbol, start_date, end_date: FakeDailyHistoryResult()


def _sample_payload() -> LowBuyScreenerResponse:
    return LowBuyScreenerResponse(
        strategy_key="first_board",
        strategy_title="首板回调",
        strategy_subtitle="",
        strategy_logic="",
        requested_mode="full",
        response_mode="full",
        as_of_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        latest_trade_date="2026-04-17",
        pool_size=100,
        scanned_count=80,
        matched_count=5,
        requested_scan_limit=48,
        active_scan_limit=480,
        full_scan_ready=True,
        full_scan_in_progress=False,
        full_scan_updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        retracement_distribution={"2天": 10},
        filters={
            "_result_version": LOW_BUY_RESULT_VERSION,
            "market_regime": "缩量无主线",
            "market_state": "low_volume_wait",
            "market_state_strength": 0.0,
            "regime_confidence": 0.0,
            "state_persistence_days": 0,
            "transition_risk": 0.0,
            "breadth_ready": False,
            "emotion_ready": False,
            "market_bonus": 0.0,
            "hot_industries_json": "[]",
            "hot_industry_source": "qa",
            "hot_industry_source_text": "QA",
            "limit_up_count": 0,
            "board_height": 0,
            "promotion_ratio": 0.0,
            "broken_board_ratio": 0.0,
            "high_flyer_retreat_ratio": 0.0,
            "stock_up_ratio": 0.0,
            "stock_median_change": 0.0,
            "style_divergence": 0.0,
            "hot_turnover": 0.0,
            "hot_overlap_ratio": 0.0,
            "previous_board_height": 0,
            "promotion_break_gap": 0.0,
            "promotion_break_pressure": 0.0,
            "high_flyer_gap_speed": 0.0,
            "distribution_pressure": 0.0,
            "mainline_lifecycle_state": "unknown",
            "mainline_lifecycle_text": "未知",
            "structure_mode": "qa",
        },
        strategy_notes=[],
        performance=None,
        confirmed_candidates=[],
        history_sections=[],
        candidates=[],
    )


def _sample_close_review_item() -> LowBuyCloseReviewItemOut:
    return LowBuyCloseReviewItemOut(
        symbol="000001",
        name="平安银行",
        signal_state="near_entry",
        signal_text="接近买点",
        review_trade_date="2026-04-17",
        close_price=12.345,
        change_pct=1.23,
        amplitude_pct=3.21,
        entry_zone_low=12.0,
        entry_zone_high=12.4,
        stop_loss=11.6,
        entry_distance_pct=0.0,
        entry_distance_text="收盘落在买点区内",
        close_vs_stop_pct=6.42,
        review_level="neutral",
        review_text="收盘进入买点区，但确认还差一步。",
    )


def _assert_daily_history_persistence(service: LowBuyScreenerService) -> None:
    history = service._load_daily_history("000001", "2026-04-17", history_window_days=180)
    assert history is not None and len(history) >= 60, "daily history should load from fake remote source"

    with SessionLocal() as db:
        stored_count = len(
            db.execute(select(DailyBarSnapshot).where(DailyBarSnapshot.symbol == "000001")).scalars().all()
        )
        assert stored_count >= 60, "daily bar snapshots were not persisted"


def _assert_pool_persistence(service: LowBuyScreenerService) -> None:
    with SessionLocal() as db:
        service._persist_pool(
            db=db,
            latest_trade_date="2026-04-17",
            pooled_candidates={
                "000001": BoardCandidate(
                    symbol="000001",
                    name="平安银行",
                    board_date="2026-04-14",
                    board_count=1,
                    amount=123000000.0,
                    industry="银行",
                )
            },
        )
        persisted_pool = service._load_persisted_pool(db=db, latest_trade_date="2026-04-17")
        assert persisted_pool is not None and "000001" in persisted_pool, "pool snapshots were not persisted"
        pool_rows = len(
            db.execute(
                select(LowBuyPoolSnapshot).where(LowBuyPoolSnapshot.latest_trade_date == "2026-04-17")
            ).scalars().all()
        )
        assert pool_rows == 1, "low buy pool snapshot row count mismatch"


def _assert_result_persistence(service: LowBuyScreenerService, payload: LowBuyScreenerResponse) -> None:
    with SessionLocal() as db:
        service._save_persisted_full_result(db=db, payload=payload, limit=16, include_history=False)
        loaded = service._load_cached_full_result(
            db=db,
            strategy="first_board",
            latest_trade_date="2026-04-17",
            limit=16,
            include_history=False,
        )
        assert loaded is not None, "persisted full scan result did not load back"
        assert loaded.response_mode == "full", "persisted full scan response_mode mismatch"

        scan_snapshot = db.execute(
            select(LowBuyScanSnapshot).where(
                LowBuyScanSnapshot.latest_trade_date == "2026-04-17",
                LowBuyScanSnapshot.strategy_key == "first_board",
            )
        ).scalar_one_or_none()
        assert scan_snapshot is not None, "materialized low buy scan snapshot missing"

        result_rows = db.execute(
            select(LowBuyResultSnapshot).where(
                LowBuyResultSnapshot.latest_trade_date == "2026-04-17",
                LowBuyResultSnapshot.strategy_key == "first_board",
            )
        ).scalars().all()
        assert isinstance(result_rows, list), "materialized low buy result rows query failed"


def _assert_performance_persistence(service: LowBuyScreenerService) -> None:
    with SessionLocal() as db:
        performance_payload = service._empty_strategy_performance(target_profit_pct=3.0, lookback_days=5)
        service._save_strategy_performance_snapshot(
            db=db,
            strategy="first_board",
            latest_trade_date="2026-04-17",
            payload=performance_payload,
        )
        performance_snapshot = db.execute(
            select(LowBuyStrategyPerformanceSnapshot).where(
                LowBuyStrategyPerformanceSnapshot.latest_trade_date == "2026-04-17",
                LowBuyStrategyPerformanceSnapshot.strategy_key == "first_board",
            )
        ).scalar_one_or_none()
        performance_window_snapshot = db.execute(
            select(LowBuyStrategyPerformanceWindowSnapshot).where(
                LowBuyStrategyPerformanceWindowSnapshot.latest_trade_date == "2026-04-17",
                LowBuyStrategyPerformanceWindowSnapshot.strategy_key == "first_board",
                LowBuyStrategyPerformanceWindowSnapshot.lookback_days == performance_payload.lookback_days,
            )
        ).scalar_one_or_none()
        assert performance_snapshot is not None or performance_window_snapshot is not None, (
            "materialized low buy performance snapshot missing"
        )


def _assert_close_review_persistence(service: LowBuyScreenerService, payload: LowBuyScreenerResponse) -> None:
    with SessionLocal() as db:
        service._save_close_review_snapshot(
            db=db,
            strategy="first_board",
            latest_trade_date="2026-04-17",
            items=[_sample_close_review_item()],
        )
        close_review_rows = db.execute(
            select(LowBuyCloseReviewSnapshot).where(
                LowBuyCloseReviewSnapshot.latest_trade_date == "2026-04-17",
                LowBuyCloseReviewSnapshot.strategy_key == "first_board",
            )
        ).scalars().all()
        assert len(close_review_rows) == 1, "materialized low buy close review snapshot missing"
        attached_payload = service._attach_close_review_snapshot(
            db=db,
            payload=payload,
            review_trade_date="2026-04-17",
        )
        assert attached_payload.close_review_items, "close review snapshot did not attach back to payload"


def main() -> None:
    init_db()
    service = LowBuyScreenerService()
    service._daily_history_cache.clear()
    service._screen_cache.clear()
    _install_fake_history(service)

    payload = _sample_payload()
    _assert_daily_history_persistence(service)
    _assert_pool_persistence(service)
    _assert_result_persistence(service, payload)
    _assert_performance_persistence(service)
    _assert_close_review_persistence(service, payload)
    print("qa-low-buy-persistence:ok")


if __name__ == "__main__":
    main()
