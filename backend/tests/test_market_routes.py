from __future__ import annotations

import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import market
from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.timezone import beijing_today
from app.models.base import Base
from app.models.entities import MarketPulseEvent, MarketReviewReport


def _override_user():
    class UserStub:
        id = 1
        username = "tester"
        is_active = True

    return UserStub()


class MarketRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_market_data = market.market_data
        market.market_data = SimpleNamespace(
            get_market_regime_fast=self._regime,
            get_market_regime=self._regime,
            sector_relative_strength_rank=lambda *_args, **_kwargs: SimpleNamespace(
                updated_at="2026-05-25 10:30:00",
                trade_date="2026-05-25",
                sector_count=1,
                items=[SimpleNamespace(leader_score=82.0, sector_name="半导体")],
                notes=[],
            ),
        )
        app = FastAPI()
        app.include_router(market.router, prefix="/api")
        app.dependency_overrides[get_current_user] = _override_user
        app.dependency_overrides[get_db] = lambda: SimpleNamespace(
            execute=lambda *_args, **_kwargs: SimpleNamespace(scalar_one_or_none=lambda: None)
        )
        self.client = TestClient(app)

    def tearDown(self) -> None:
        market.market_data = self.original_market_data

    def test_market_breadth_returns_compact_payload(self) -> None:
        response = self.client.get("/api/market/breadth")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["state_text"], "震荡修复")
        self.assertEqual(body["hot_industries"], ["半导体"])
        self.assertEqual(body["data_quality"], "fresh")
        self.assertEqual(body["hourly_all_market_snapshot"], {})

    def test_market_pulse_returns_partial_when_hourly_snapshot_missing(self) -> None:
        response = self.client.get("/api/market/pulse")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn(body["data_quality"], {"partial", "fresh"})
        self.assertIn("龙头", body["leader_strength_text"])
        self.assertIn("hourly_all_market_snapshot", [item["source"] for item in body["partial_errors"]])

    def test_market_pulse_read_does_not_write_history(self) -> None:
        engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine, future=True)

        app = FastAPI()
        app.include_router(market.router, prefix="/api")
        app.dependency_overrides[get_current_user] = _override_user

        def _db_override():
            with Session() as db:
                yield db

        app.dependency_overrides[get_db] = _db_override
        client = TestClient(app)

        self.assertEqual(client.get("/api/market/pulse").status_code, 200)
        self.assertEqual(client.get("/api/market/pulse").status_code, 200)

        with Session() as db:
            count = db.query(MarketPulseEvent).count()
        self.assertEqual(count, 0)

    def test_market_pulse_history_lists_recorded_events(self) -> None:
        engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine, future=True)
        with Session() as db:
            db.add(
                MarketPulseEvent(
                    trade_date="2026-05-25",
                    pulse_level="repair",
                    data_quality="partial",
                    pulse_text="市场修复",
                    suggested_action="小仓确认",
                    payload_json='{"pulse_level":"repair"}',
                )
            )
            db.commit()

        app = FastAPI()
        app.include_router(market.router, prefix="/api")
        app.dependency_overrides[get_current_user] = _override_user
        def _db_override():
            with Session() as db:
                yield db

        app.dependency_overrides[get_db] = _db_override
        client = TestClient(app)

        response = client.get("/api/market/pulse/history?trade_date=2026-05-25")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["items"][0]["pulse_level"], "repair")

    def test_market_review_summary_endpoint_is_market_scoped(self) -> None:
        engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine, future=True)
        review_date = beijing_today()
        with Session() as db:
            db.add(
                MarketReviewReport(
                    report_date=review_date,
                    report_slot="midday",
                    overall_summary="午盘市场复盘：全市场温和修复",
                    strategy_highlights="[]",
                    risk_alerts='[{"level":"warning","content":"控制追高"}]',
                    suggestion="午后控制追高",
                    raw_metrics_snapshot="{}",
                    llm_model="market-rule",
                )
            )
            db.commit()

        app = FastAPI()
        app.include_router(market.router, prefix="/api")
        app.dependency_overrides[get_current_user] = _override_user

        def _db_override():
            with Session() as db:
                yield db

        app.dependency_overrides[get_db] = _db_override
        client = TestClient(app)

        response = client.get("/api/market/review-summary")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["review_status"]["source_scope"], "market")
        self.assertEqual(body["review_status"]["review_subject"], "全市场")
        self.assertEqual(body["review_reports"][0]["report_slot"], "midday")

    def test_market_trading_session_returns_backend_calendar_status(self) -> None:
        response = self.client.get("/api/market/trading-session")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("is_trading_day", body)
        self.assertIn("is_trading_now", body)
        self.assertEqual(body["timezone"], "Asia/Shanghai")

    @staticmethod
    def _regime():
        return SimpleNamespace(
            state="repair",
            label="震荡修复",
            breadth_ready=True,
            emotion_ready=True,
            stock_up_ratio=0.58,
            stock_median_change=0.42,
            largecap_change=0.2,
            smallcap_change=0.5,
            style_divergence=0.3,
            limit_up_count=48,
            limit_down_count=2,
            broken_board_ratio=0.16,
            promotion_ratio=0.35,
            board_height=5,
            hot_industries=["半导体"],
            hot_turnover=1.2,
            hot_overlap_ratio=0.6,
        )


if __name__ == "__main__":
    unittest.main()
