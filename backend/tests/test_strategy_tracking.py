from __future__ import annotations

import json
import unittest
from decimal import Decimal

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
    Instrument,
    LowBuyResultSnapshot,
    LowBuyTradeLifecycleSnapshot,
    MarketModelObservation,
    PaperOrder,
    StrategyMetadata,
    StrategyTrackingSnapshot,
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
        self.assertEqual(item["board_type"], "main")
        self.assertEqual(item["board_type_text"], "主板")
        self.assertIn("主板", item["display_sectors"])
        self.assertIn("plain_language_summary", item)
        self.assertEqual(item["sector_detail"]["board_type_text"], "主板")

    def test_board_detection_filters_and_sector_degrade(self) -> None:
        self._seed_board_fixture()

        response = self.client.get("/api/strategy-tracking/items?range=10&limit=10")
        self.assertEqual(response.status_code, 200)
        items = {item["symbol"]: item for item in response.json()["items"]}
        self.assertEqual(items["600000"]["board_type"], "main")
        self.assertEqual(items["300001"]["board_type"], "chinext")
        self.assertEqual(items["688001"]["board_type"], "star")
        self.assertIn("银行", items["600000"]["industry_sectors"])
        self.assertIn("金融科技", items["600000"]["concept_sectors"])
        self.assertIn("新能源", items["300001"]["industry_sectors"])
        self.assertIn("科创板", items["688001"]["display_sectors"])
        self.assertEqual(items["600003"]["display_sectors"], ["主板"])
        self.assertEqual(items["300001"]["user_friendly_status"], "take_profit_watch")

        exclude_chinext = self.client.get("/api/strategy-tracking/items?range=10&limit=10&exclude_chinext=true")
        self.assertEqual(exclude_chinext.status_code, 200)
        self.assertNotIn("300001", {item["symbol"] for item in exclude_chinext.json()["items"]})

        exclude_star = self.client.get("/api/strategy-tracking/items?range=10&limit=10&exclude_star=true")
        self.assertEqual(exclude_star.status_code, 200)
        self.assertNotIn("688001", {item["symbol"] for item in exclude_star.json()["items"]})

        main_only = self.client.get("/api/strategy-tracking/items?range=10&limit=10&board_filter=main_only")
        self.assertEqual(main_only.status_code, 200)
        self.assertEqual({item["symbol"] for item in main_only.json()["items"]}, {"600000", "600003"})

    def test_holding_analysis_aggregates_by_strategy_and_is_read_only(self) -> None:
        self._seed_board_fixture()
        with self.Session() as db:
            strategy_before = db.query(LowBuyResultSnapshot).count()
            orders_before = db.query(PaperOrder).count()

        response = self.client.get("/api/strategy-tracking/holding-analysis?range=10")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["production_writeable"])
        rows = {item["strategy_key"]: item for item in body["items"]}
        self.assertIn("first_board", rows)
        self.assertEqual(rows["first_board"]["sample_count"], 3)
        self.assertGreater(rows["first_board"]["avg_best_holding_days"], 0)
        self.assertIn(rows["first_board"]["dominant_holding_bucket"], {"short_1_3d", "swing_4_10d"})
        self.assertIn("首板回调", rows["first_board"]["conclusion"])
        self.assertGreaterEqual(rows["first_board"]["short_hold_ratio"], 0)
        self.assertIn("volume_shrink", rows)
        self.assertEqual(rows["volume_shrink"]["dominant_holding_bucket"], "unavailable")
        self.assertEqual(rows["volume_shrink"]["dominant_holding_bucket_text"], "样本不足")

        filtered = self.client.get("/api/strategy-tracking/holding-analysis?range=10&exclude_chinext=true&exclude_star=true")
        self.assertEqual(filtered.status_code, 200)
        first_board = next(item for item in filtered.json()["items"] if item["strategy_key"] == "first_board")
        self.assertEqual(first_board["sample_count"], 1)
        with self.Session() as db:
            self.assertEqual(db.query(LowBuyResultSnapshot).count(), strategy_before)
            self.assertEqual(db.query(PaperOrder).count(), orders_before)

    def test_tracking_read_model_cache_reuses_bars_for_same_window(self) -> None:
        self._seed_board_fixture()
        from app.services.strategy_tracking import StrategyTrackingService, clear_strategy_tracking_read_cache

        clear_strategy_tracking_read_cache()
        with self.Session() as db:
            service = StrategyTrackingService(db)
            original_fetch = service._fetch_light_bars
            calls = 0

            def counting_fetch(*args, **kwargs):  # noqa: ANN002, ANN003
                nonlocal calls
                calls += 1
                return original_fetch(*args, **kwargs)

            service._fetch_light_bars = counting_fetch  # type: ignore[method-assign]
            first = service.list_items(range_days=10, limit=10)
            second = service.list_items(range_days=10, limit=10)

        self.assertEqual(first.total, second.total)
        self.assertEqual(calls, 1)

    def test_holding_analysis_reuses_tracking_read_model_cache(self) -> None:
        self._seed_board_fixture()
        from app.services.strategy_tracking import StrategyTrackingService, clear_strategy_tracking_read_cache

        clear_strategy_tracking_read_cache()
        with self.Session() as db:
            service = StrategyTrackingService(db)
            service.list_items(range_days=10, limit=10)
            original_fetch = service._fetch_light_bars
            calls = 0

            def counting_fetch(*args, **kwargs):  # noqa: ANN002, ANN003
                nonlocal calls
                calls += 1
                return original_fetch(*args, **kwargs)

            service._fetch_light_bars = counting_fetch  # type: ignore[method-assign]
            holding = service.holding_analysis(range_days=10)

        self.assertTrue(holding.items)
        self.assertEqual(calls, 0)

    def test_snapshot_missing_does_not_recompute_on_public_read(self) -> None:
        self._seed_board_fixture()
        from app.services.strategy_tracking_snapshot import StrategyTrackingSnapshotBuilder

        with self.Session() as db:
            builder = StrategyTrackingSnapshotBuilder(db)

            def fail_load(*args, **kwargs):  # noqa: ANN002, ANN003
                raise AssertionError("snapshot read must not rebuild synchronously")

            builder._latest_snapshot = fail_load  # type: ignore[method-assign]
            with self.assertRaises(AssertionError):
                builder.get_snapshot(range_days=10)

        response = self.client.get("/api/strategy-tracking/snapshot?range=10&limit=10")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "missing")
        self.assertTrue(body["stale"])
        self.assertEqual(body["payload"]["items"], [])
        self.assertIn("strategy_tracking_snapshot_missing", body["partial_errors"])

    def test_snapshot_rebuild_writes_read_model_and_snapshot_filters_from_it(self) -> None:
        self._seed_board_fixture()

        rebuild = self.client.post("/api/strategy-tracking/snapshot/rebuild?range=10", headers={"X-Admin-Token": "test-admin-token"})
        self.assertEqual(rebuild.status_code, 200)
        rebuild_body = rebuild.json()
        self.assertTrue(rebuild_body["ok"])
        self.assertGreaterEqual(rebuild_body["item_count"], 4)

        response = self.client.get("/api/strategy-tracking/snapshot?range=10&limit=10&exclude_chinext=true&exclude_star=true")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "fresh")
        self.assertFalse(body["production_writeable"])
        self.assertEqual({item["symbol"] for item in body["payload"]["items"]}, {"600000", "600003"})
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["payload"]["audit"]["future_leak_check"], "passed")
        self.assertIn("generated_at", body)
        self.assertIn("source_data_cutoff", body)
        self.assertIn("data_version", body)

    def test_snapshot_rebuild_failure_keeps_previous_fresh_snapshot(self) -> None:
        self._seed_tracking_fixture()
        from app.services import strategy_tracking_snapshot as snapshot_module

        ok = self.client.post("/api/strategy-tracking/snapshot/rebuild?range=10", headers={"X-Admin-Token": "test-admin-token"})
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(ok.json()["ok"])

        original_audit = snapshot_module._audit_items

        def failing_audit(items):  # noqa: ANN001
            audit = original_audit(items)
            audit.violation_count = 1
            audit.audit_flags = ["forced_violation"]
            return audit

        snapshot_module._audit_items = failing_audit  # type: ignore[assignment]
        try:
            failed = self.client.post("/api/strategy-tracking/snapshot/rebuild?range=10", headers={"X-Admin-Token": "test-admin-token"})
        finally:
            snapshot_module._audit_items = original_audit  # type: ignore[assignment]

        self.assertEqual(failed.status_code, 200)
        self.assertFalse(failed.json()["ok"])
        self.assertTrue(failed.json()["stale_snapshot_used"])

        response = self.client.get("/api/strategy-tracking/snapshot?range=10&limit=10")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "fresh")
        with self.Session() as db:
            row = db.query(StrategyTrackingSnapshot).one()
            self.assertEqual(row.status, "fresh")
            self.assertIn("防未来函数校验失败", row.error_message)

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
        self.assertEqual(body["storage_mode"], "snapshot_read_model_no_strategy_write")
        self.assertFalse(body["changed_strategy_results"])
        self.assertFalse(body["changed_paper_ledger"])
        with self.Session() as db:
            self.assertEqual(db.query(StrategyTrackingSnapshot).count(), 1)
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

    def _seed_board_fixture(self) -> None:
        with self.Session() as db:
            self._seed_metadata(db)
            db.add_all(
                [
                    Instrument(symbol="600000", name="浦发银行", market="CN", instrument_type="stock", sector_name="银行"),
                    Instrument(symbol="300001", name="创业成长", market="CN", instrument_type="stock", sector_name="新能源"),
                    Instrument(symbol="688001", name="科创芯片", market="CN", instrument_type="stock", sector_name="半导体"),
                    Instrument(symbol="600003", name="缺失板块", market="CN", instrument_type="stock", sector_name=""),
                    LowBuyResultSnapshot(
                        latest_trade_date="2026-04-20",
                        strategy_key="first_board",
                        symbol="600000",
                        name="浦发银行",
                        score=90,
                        buy_signal_state="buy_now",
                        payload_json=json.dumps(
                            _payload(price=10.0, sector_name="银行", concept_sectors=["金融科技", "中特估"]),
                            ensure_ascii=False,
                        ),
                    ),
                    LowBuyResultSnapshot(
                        latest_trade_date="2026-04-20",
                        strategy_key="first_board",
                        symbol="300001",
                        name="创业成长",
                        score=88,
                        buy_signal_state="buy_now",
                        payload_json=json.dumps(
                            _payload(price=20.0, entry_low=19.0, entry_high=20.5, stop_loss=18.0, target_price=23.0),
                            ensure_ascii=False,
                        ),
                    ),
                    LowBuyResultSnapshot(
                        latest_trade_date="2026-04-20",
                        strategy_key="first_board",
                        symbol="688001",
                        name="科创芯片",
                        score=87,
                        buy_signal_state="buy_now",
                        payload_json=json.dumps(
                            _payload(price=30.0, entry_low=29.0, entry_high=31.0, stop_loss=27.0, target_price=34.0),
                            ensure_ascii=False,
                        ),
                    ),
                    LowBuyResultSnapshot(
                        latest_trade_date="2026-04-20",
                        strategy_key="volume_shrink",
                        symbol="600003",
                        name="缺失板块",
                        score=80,
                        buy_signal_state="buy_now",
                        payload_json=json.dumps(_payload(price=12.0, without_sector=True), ensure_ascii=False),
                    ),
                    _paper_order("600000"),
                    _bar("600000", "2026-04-19", high=10.3, low=9.8, close=10.0),
                    _bar("600000", "2026-04-20", high=10.4, low=9.9, close=10.0),
                    _bar("600000", "2026-04-21", high=11.1, low=9.7, close=10.8),
                    _bar("600000", "2026-04-22", high=10.9, low=10.2, close=10.4),
                    _bar("300001", "2026-04-19", high=20.4, low=19.8, close=20.0),
                    _bar("300001", "2026-04-20", high=20.5, low=19.5, close=20.0),
                    _bar("300001", "2026-04-21", high=22.0, low=19.2, close=21.5),
                    _bar("300001", "2026-04-22", high=22.8, low=21.0, close=22.4),
                    _bar("688001", "2026-04-19", high=30.4, low=29.8, close=30.0),
                    _bar("688001", "2026-04-20", high=30.5, low=29.5, close=30.0),
                    _bar("688001", "2026-04-21", high=33.0, low=29.3, close=31.5),
                    _bar("688001", "2026-04-22", high=32.0, low=30.0, close=30.8),
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
                StrategyMetadata(
                    key="volume_shrink",
                    display_name="缩量回踩",
                    category="core",
                    enabled=True,
                    visibility="full",
                ),
            ]
        )


def _payload(
    price: float,
    *,
    entry_low: float = 9.5,
    entry_high: float = 10.5,
    stop_loss: float = 9.0,
    target_price: float = 11.0,
    sector_name: str = "",
    concept_sectors: list[str] | None = None,
    without_sector: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "strategy_title": "首板回调",
        "latest_price": price,
        "entry_zone_low": entry_low,
        "entry_zone_high": entry_high,
        "stop_loss": stop_loss,
        "take_profit": target_price,
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
    if not without_sector:
        payload["sector_name"] = sector_name or "银行"
        payload["concept_sectors"] = concept_sectors or ["金融科技"]
    return payload


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


def _paper_order(symbol: str) -> PaperOrder:
    return PaperOrder(
        account_id=1,
        symbol=symbol,
        name="只读检查",
        side="buy",
        order_type="market",
        price=Decimal("10.0"),
        quantity=100,
        filled_quantity=0,
        status="pending",
        source="unit-test",
        strategy_key="first_board",
    )


if __name__ == "__main__":
    unittest.main()
