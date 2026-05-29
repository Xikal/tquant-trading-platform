from __future__ import annotations

import json
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import strategy_tracking
from app.core.admin_auth import require_admin_auth
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.base import Base
from app.models.entities import (
    DailyBarSnapshot,
    LowBuyResultSnapshot,
    LowBuyTradeLifecycleSnapshot,
    MarketModelObservation,
    StrategyMetadata,
)


def _override_user():
    class UserStub:
        id = 1
        username = "tester"
        is_active = True

    return UserStub()


class StrategyTrackingTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, future=True)
        app = FastAPI()
        app.include_router(strategy_tracking.router, prefix="/api")
        app.dependency_overrides[get_current_user] = _override_user
        app.dependency_overrides[require_admin_auth] = lambda: None

        def override_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def test_items_filter_production_strategy_and_isolate_signal_day(self) -> None:
        self._seed_tracking_fixture()

        response = self.client.get("/api/strategy-tracking/items?range=10&limit=10")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 1)
        item = body["items"][0]
        self.assertEqual(item["strategy_key"], "first_board")
        self.assertEqual(item["first_signal_date"], "2026-04-20")
        self.assertTrue(item["entry_touched"])
        self.assertTrue(item["stop_triggered"])
        self.assertEqual(item["stop_triggered_date"], "2026-04-22")
        self.assertEqual(item["max_gain_pct"], 10.0)
        self.assertEqual(item["max_drawdown_pct"], -16.19)
        self.assertEqual(item["lifecycle_status"], "stopped")
        self.assertFalse(body["production_writeable"])
        self.assertTrue(body["rust_math_used"])

    def test_detail_is_lazy_and_returns_compact_snapshot(self) -> None:
        self._seed_tracking_fixture()

        item_id = "first_board:600000:2026-04-20"
        response = self.client.get(f"/api/strategy-tracking/items/{item_id}")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["item"]["id"], item_id)
        self.assertEqual([point["trade_date"] for point in body["timeline"]], ["2026-04-21", "2026-04-22"])
        self.assertEqual(
            {marker["kind"] for marker in body["markers"]},
            {"first_signal", "target", "stop", "highest", "lowest", "best_exit"},
        )
        self.assertNotIn("payload_json", body["signal_snapshot"])
        self.assertIn("summary_reason", body["signal_snapshot"])

    def test_items_include_attribution_audit_and_holding_fields(self) -> None:
        self._seed_tracking_fixture()

        response = self.client.get("/api/strategy-tracking/items?range=10&limit=10")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        item = body["items"][0]
        self.assertIn("stop_loss_triggered", item["failure_tags"])
        self.assertEqual(item["market_state"], "strong_market")
        self.assertEqual(item["sector_state"], "sector_main_rise")
        self.assertEqual(item["future_leak_check"], "needs_review")
        self.assertTrue(item["needs_review"])
        self.assertGreaterEqual(item["best_holding_days"], 1)
        self.assertIsNotNone(item["best_exit_date"])
        self.assertIn("market_segments", body)
        self.assertIn("shadow_observations", body)

    def test_shadow_zero_samples_report_reason(self) -> None:
        self._seed_tracking_fixture()

        response = self.client.get("/api/strategy-tracking/shadow-observations?range=10&model_key=main_force_model_observation")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body[0]["observation_count"], 0)
        self.assertEqual(body[0]["no_sample_reason"], "no_model_observation")
        self.assertIn("没有该模型观测记录", body[0]["no_sample_reason_text"])

    def test_shadow_no_sample_reason_diagnoses_observation_blockers(self) -> None:
        self._seed_tracking_fixture()
        cases = [
            ("strategy_disabled", {"strategy_enabled": False}, "策略未启用"),
            ("window_not_reached", {"shadow_status": "pending_window"}, "时间窗口尚未满足"),
            ("shadow_job_not_run", {"job_status": "not_run"}, "Shadow 任务未运行"),
            ("write_failed", {"write_failed": True}, "观测写入失败"),
            ("schema_mismatch", "{bad-json", "字段或模型版本不匹配"),
        ]
        with self.Session() as db:
            for reason, payload, _text in cases:
                db.add(
                    MarketModelObservation(
                        model_key=reason,
                        symbol="600009",
                        name="Shadow 阻塞样本",
                        trade_date="2026-04-21",
                        signal_state="",
                        payload_json=payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False),
                    )
                )
            db.commit()

        for reason, _payload, text in cases:
            response = self.client.get(f"/api/strategy-tracking/shadow-observations?range=10&model_key={reason}")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body[0]["no_sample_reason"], reason)
            self.assertIn(text, body[0]["no_sample_reason_text"])

    def test_shadow_no_sample_reason_diagnoses_no_qualified_signal_and_data_missing(self) -> None:
        with self.Session() as db:
            db.add(
                MarketModelObservation(
                    model_key="no_signal_model",
                    symbol="600010",
                    name="无合格信号",
                    trade_date="2026-04-21",
                    signal_state="watch",
                    payload_json="{}",
                )
            )
            db.add(
                MarketModelObservation(
                    model_key="data_missing_model",
                    symbol="",
                    name="数据缺失",
                    trade_date="",
                    signal_state="watch",
                    payload_json="{}",
                )
            )
            db.commit()

        no_signal = self.client.get("/api/strategy-tracking/shadow-observations?range=10&model_key=no_signal_model")
        data_missing = self.client.get("/api/strategy-tracking/shadow-observations?range=10&model_key=data_missing_model")

        self.assertEqual(no_signal.status_code, 200)
        self.assertEqual(no_signal.json()[0]["no_sample_reason"], "no_qualified_signal")
        self.assertIn("没有符合条件信号", no_signal.json()[0]["no_sample_reason_text"])
        self.assertEqual(data_missing.status_code, 200)
        self.assertEqual(data_missing.json()[0]["no_sample_reason"], "data_missing")
        self.assertIn("缺少可关联标的", data_missing.json()[0]["no_sample_reason_text"])

    def test_review_audit_and_report_endpoints_are_read_only(self) -> None:
        self._seed_tracking_fixture()
        with self.Session() as db:
            before = db.query(LowBuyResultSnapshot).count()

        review = self.client.get("/api/strategy-tracking/review?range=10")
        audit = self.client.get("/api/strategy-tracking/leakage-audit?range=10&needs_review=true")
        daily_report = self.client.get("/api/strategy-tracking/reports/daily?range=10")
        report = self.client.get("/api/strategy-tracking/reports/weekly?range=10")

        self.assertEqual(review.status_code, 200)
        self.assertIn("stop_loss_triggered", review.json()["failure_tags"])
        self.assertEqual(audit.status_code, 200)
        self.assertGreaterEqual(len(audit.json()["needs_review_items"]), 1)
        self.assertEqual(daily_report.status_code, 200)
        self.assertIn("策略跟踪日报", daily_report.json()["markdown"])
        self.assertEqual(report.status_code, 200)
        self.assertIn("策略跟踪周报", report.json()["markdown"])
        with self.Session() as db:
            after = db.query(LowBuyResultSnapshot).count()
        self.assertEqual(after, before)

    def test_bad_payload_and_missing_bars_degrade_without_blocking_other_items(self) -> None:
        with self.Session() as db:
            self._seed_metadata(db)
            db.add(
                LowBuyResultSnapshot(
                    latest_trade_date="2026-04-20",
                    strategy_key="first_board",
                    symbol="600001",
                    name="坏数据",
                    score=88,
                    buy_signal_state="buy_now",
                    payload_json="{bad-json",
                )
            )
            db.commit()

        response = self.client.get("/api/strategy-tracking/items?range=10&limit=10")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["items"][0]["data_quality"], "partial")
        self.assertEqual(body["items"][0]["lifecycle_status"], "data_unavailable")
        self.assertIn("payload_json_invalid", body["partial_errors"][0])

    def test_limit_above_50_is_rejected_by_route(self) -> None:
        response = self.client.get("/api/strategy-tracking/items?limit=80")

        self.assertEqual(response.status_code, 422)

    def test_refresh_is_read_through_and_does_not_mutate_strategy_outputs(self) -> None:
        self._seed_tracking_fixture()
        with self.Session() as db:
            before = db.query(LowBuyResultSnapshot).count()

        response = self.client.post("/api/strategy-tracking/refresh?range=10", headers={"X-Admin-Token": "test-admin-token"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["storage_mode"], "read_through_view_no_strategy_write")
        self.assertFalse(body["changed_strategy_results"])
        self.assertFalse(body["changed_paper_ledger"])
        with self.Session() as db:
            after = db.query(LowBuyResultSnapshot).count()
        self.assertEqual(after, before)

    def _seed_tracking_fixture(self) -> None:
        with self.Session() as db:
            self._seed_metadata(db)
            db.add_all(
                [
                    LowBuyResultSnapshot(
                        latest_trade_date="2026-04-20",
                        strategy_key="first_board",
                        symbol="600000",
                        name="浦发银行",
                        score=90,
                        buy_signal_state="near_entry",
                        payload_json=json.dumps(_payload(price=10.0), ensure_ascii=False),
                    ),
                    LowBuyResultSnapshot(
                        latest_trade_date="2026-04-21",
                        strategy_key="first_board",
                        symbol="600000",
                        name="浦发银行",
                        score=95,
                        buy_signal_state="buy_now",
                        payload_json=json.dumps(_payload(price=10.2), ensure_ascii=False),
                    ),
                    LowBuyResultSnapshot(
                        latest_trade_date="2026-04-21",
                        strategy_key="classic_retrace",
                        symbol="600002",
                        name="研究策略样本",
                        score=99,
                        buy_signal_state="buy_now",
                        payload_json=json.dumps(_payload(price=10.0), ensure_ascii=False),
                    ),
                    LowBuyTradeLifecycleSnapshot(
                        signal_trade_date="2026-04-20",
                        strategy_key="first_board",
                        symbol="600000",
                        name="浦发银行",
                        signal_state="buy_now",
                        status="planned",
                        entry_plan_low=9.5,
                        entry_plan_high=10.5,
                        stop_loss=9.0,
                        take_profit=11.0,
                    ),
                    _bar("600000", "2026-04-20", high=20.0, low=8.0, close=10.0),
                    _bar("600000", "2026-04-21", high=11.0, low=9.6, close=10.5),
                    _bar("600000", "2026-04-22", high=10.4, low=8.8, close=8.8),
                    _bar("600002", "2026-04-21", high=11.0, low=9.5, close=10.5),
                ]
            )
            db.commit()

    def _seed_metadata(self, db) -> None:  # noqa: ANN001
        db.add_all(
            [
                StrategyMetadata(
                    key="first_board",
                    display_name="首板回调",
                    category="core",
                    enabled=True,
                    visibility="full",
                ),
                StrategyMetadata(
                    key="classic_retrace",
                    display_name="经典回踩",
                    category="research",
                    enabled=True,
                    visibility="full",
                ),
            ]
        )


def _payload(price: float) -> dict[str, object]:
    return {
        "strategy_title": "首板回调",
        "latest_price": price,
        "entry_zone_low": 9.5,
        "entry_zone_high": 10.5,
        "stop_loss": 9.0,
        "take_profit": 11.0,
        "summary_reason": "缩量回踩到支撑位",
        "reasons": ["回踩支撑"],
        "risks": ["跌破止损"],
        "market_state": "strong_market",
        "market_state_text": "强势行情",
        "sector_state": "sector_main_rise",
        "sector_state_text": "板块主升",
        "signal_generated_at": "2026-04-20T14:50:00+08:00",
        "data_cutoff_at": "2026-04-20T14:45:00+08:00",
        "lookback_start_date": "2026-03-20",
        "lookback_end_date": "2026-04-20",
        "data_quality": "ok",
    }


def _bar(symbol: str, trade_date: str, *, high: float, low: float, close: float) -> DailyBarSnapshot:
    return DailyBarSnapshot(
        symbol=symbol,
        market="CN",
        instrument_type="stock",
        trade_date=trade_date,
        open_price=10.0,
        close_price=close,
        high_price=high,
        low_price=low,
        volume=1000,
        amount=10000,
        pct_chg=0.0,
        source="unit-test",
        data_quality="ok",
    )


if __name__ == "__main__":
    unittest.main()
