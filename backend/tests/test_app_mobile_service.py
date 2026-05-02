from __future__ import annotations

import unittest
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.entities import Watchlist, UserWatchlist
from app.models.schemas import (
    AppLowBuyFavoriteRequest,
    AppWatchlistUpsertRequest,
    LowBuyCandidateOut,
    LowBuyScreenerResponse,
)
from app.services.app_mobile.service import AppMobileService


class _WatchlistSignalStub:
    def __init__(self, payloads: Optional[list[dict]] = None) -> None:
        self.payloads = payloads or []
        self.refresh_forced = False
        self.invalidated_symbols: list[str] = []

    def list_signals(self, db):  # noqa: ARG002
        return list(self.payloads)

    def build_live_signals(self, db, rows):  # noqa: ARG002
        by_symbol = {payload["symbol"]: payload for payload in self.payloads}
        return [by_symbol[row.symbol] for row in rows if row.symbol in by_symbol]

    def ensure_background_refresh(self, force: bool = False) -> bool:
        self.refresh_forced = force
        return force

    def invalidate_symbol(self, symbol: str) -> None:
        self.invalidated_symbols.append(symbol)


class _LowBuyScreenerStub:
    def __init__(self, payload: LowBuyScreenerResponse) -> None:
        self.payload = payload
        self.last_detail_limit: int | None = None
        self.last_fallback_scan_limit: int | None = None

    def mobile_snapshot(self, db, strategy: str, limit: int, fallback_scan_limit: int):  # noqa: ARG002
        return self.payload

    def mobile_candidate_by_symbol(self, db, symbol: str, strategy: str, detail_limit: int, fallback_scan_limit: int):  # noqa: ARG002
        self.last_detail_limit = detail_limit
        self.last_fallback_scan_limit = fallback_scan_limit
        for item in self.payload.confirmed_candidates + self.payload.candidates:
            if item.symbol == symbol:
                return item, self.payload
        return None, self.payload


def _watchlist_signal_payload(symbol: str, action: str, risk_level: str) -> dict:
    return {
        "symbol": symbol,
        "name": f"证券{symbol}",
        "base_position": 1000,
        "available_position": 800,
        "cost_basis": 3.21,
        "memo": "测试",
        "quote": {
            "symbol": symbol,
            "name": f"证券{symbol}",
            "market": "SH",
            "instrument_type": "etf",
            "last_price": 3.33,
            "change_pct": 1.2,
            "change_amount": 0.04,
            "open_price": 3.29,
            "high_price": 3.35,
            "low_price": 3.28,
            "prev_close": 3.29,
            "volume": 1000000,
            "amount": 2000000,
            "turnover_rate": None,
            "volume_ratio": None,
            "timestamp": "2026-04-22 10:00:00",
        },
        "signal": {
            "action": action,
            "entry_price": 3.3,
            "exit_price": 3.36,
            "position_pct": 25.0,
            "stop_loss": 3.24,
            "risk_level": risk_level,
            "signal_score": 72.0,
            "tradability_score": 80.0,
            "confidence": 67.0,
            "expected_profit_pct": 0.8,
            "scenario": "trend_retrace",
            "reasons": ["测试理由"],
            "blocking_rules": ["测试阻断"] if action == "hold" else [],
            "take_profit": 3.36,
            "strategy_notes": "测试策略说明",
        },
        "rules": {
            "symbol": symbol,
            "turnaround_mode": "t0",
            "supports_positive_t": True,
            "supports_negative_t": True,
            "same_day_sell_allowed": True,
            "requires_base_position": False,
            "notes": "ETF 可日内回转",
        },
        "error": None,
    }


def _candidate(symbol: str) -> LowBuyCandidateOut:
    return LowBuyCandidateOut(
        strategy_key="classic_retrace",
        strategy_title="原始低吸法",
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


def _low_buy_payload() -> LowBuyScreenerResponse:
    return LowBuyScreenerResponse(
        strategy_key="classic_retrace",
        strategy_title="原始低吸法",
        strategy_subtitle="测试副标题",
        strategy_logic="测试逻辑",
        requested_mode="full",
        response_mode="full",
        as_of_date="2026-04-22",
        latest_trade_date="2026-04-22",
        pool_size=120,
        scanned_count=48,
        matched_count=2,
        requested_scan_limit=48,
        active_scan_limit=48,
        full_scan_ready=True,
        full_scan_in_progress=False,
        full_scan_updated_at="2026-04-22 10:05:00",
        retracement_distribution={"2天": 1, "3天": 1},
        filters={"scan_mode": "full"},
        strategy_notes=["测试说明"],
        performance=None,
        close_review_trade_date=None,
        close_review_updated_at=None,
        close_review_items=[],
        confirmed_candidates=[_candidate("300750")],
        history_sections=[],
        candidates=[_candidate("002594")],
    )
class AppMobileServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, future=True)
        self.service = AppMobileService()
        self.service.watchlist_signal_service = _WatchlistSignalStub(
            [
                _watchlist_signal_payload("510300", "positive_t", "medium"),
                _watchlist_signal_payload("159915", "hold", "high"),
            ]
        )
        self.service.low_buy_screener = _LowBuyScreenerStub(_low_buy_payload())

    def test_home_aggregates_summary(self) -> None:
        with self.Session() as db:
            payload = self.service.home(db)
        self.assertEqual(payload.summary.total, 2)
        self.assertEqual(payload.summary.positive_t_count, 1)
        self.assertEqual(payload.summary.hold_count, 1)
        self.assertEqual(payload.summary.high_risk_count, 1)
        self.assertEqual(len(payload.items), 2)
        self.assertEqual(payload.items[0].plain_action_text, "现在能买回")
        self.assertIn("触发价", payload.items[0].plain_action_reason)
        self.assertIn("买入", payload.items[0].plain_execution_text)
        self.assertTrue(payload.items[0].plain_invalid_condition)

    def test_watchlist_crud_uses_shared_logic(self) -> None:
        with self.Session() as db:
            created = self.service.upsert_watchlist(
                AppWatchlistUpsertRequest(symbol="510300", name="沪深300ETF", memo="加入自选"),
                db,
            )
        self.assertEqual(created.symbol, "510300")
        self.assertEqual(created.message, "自选股已保存")

    def test_app_watchlist_isolated_by_user_id(self) -> None:
        with self.Session() as db:
            self.service.upsert_watchlist(
                AppWatchlistUpsertRequest(symbol="510300", name="沪深300ETF", memo="用户1"),
                db,
                user_id=1,
            )
            self.service.upsert_watchlist(
                AppWatchlistUpsertRequest(symbol="159915", name="创业板ETF", memo="用户2"),
                db,
                user_id=2,
            )

            user_one = self.service.list_watchlist(db, user_id=1)
            user_two = self.service.list_watchlist(db, user_id=2)
            global_rows = db.query(UserWatchlist).count()

        self.assertEqual(global_rows, 2)
        self.assertEqual([item.symbol for item in user_one.items], ["510300"])
        self.assertEqual([item.symbol for item in user_two.items], ["159915"])

    def test_watchlist_list_and_detail(self) -> None:
        with self.Session() as db:
            db.add(
                Watchlist(
                    symbol="510300",
                    name="沪深300ETF",
                    base_position=1200,
                    available_position=800,
                    cost_basis=3.456,
                    memo="观察仓",
                )
            )
            db.commit()
            listing = self.service.list_watchlist(db)
            detail = self.service.get_watchlist_detail("510300", db)
        self.assertEqual(len(listing.items), 1)
        self.assertEqual(detail.symbol, "510300")
        self.assertTrue(detail.detail_sections.reasons)

    def test_low_buy_summary_and_detail(self) -> None:
        with self.Session() as db:
            summary = self.service.low_buy(db, strategy="classic_retrace", limit=12, scan_limit=48, scan_mode="full")
            detail = self.service.get_low_buy_detail("300750", db, strategy="classic_retrace", scan_limit=72)
        self.assertEqual(summary.strategy.strategy_key, "classic_retrace")
        self.assertEqual(len(summary.confirmed_candidates), 1)
        self.assertEqual(len(summary.priority_board.items), 2)
        self.assertEqual(len(summary.priority_board.family_sections), 1)
        self.assertEqual(summary.priority_board.family_sections[0].family_text, "趋势回调低吸")
        self.assertEqual(detail.candidate.symbol, "300750")
        self.assertFalse(detail.favorite_status.in_watchlist)
        self.assertEqual(self.service.low_buy_screener.last_detail_limit, 24)
        self.assertEqual(self.service.low_buy_screener.last_fallback_scan_limit, 72)

    def test_low_buy_favorite_reuses_watchlist_upsert(self) -> None:
        with self.Session() as db:
            result = self.service.favorite_low_buy(
                "300750",
                AppLowBuyFavoriteRequest(name="宁德时代", memo="来自选股宝典"),
                db,
            )
            row = db.query(Watchlist).filter(Watchlist.symbol == "300750").one_or_none()
        self.assertEqual(result.symbol, "300750")
        self.assertEqual(result.message, "自选股已保存")
        self.assertIsNotNone(row)


if __name__ == "__main__":
    unittest.main()
