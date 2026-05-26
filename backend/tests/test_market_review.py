from __future__ import annotations

import json
from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.entities import MarketHourlySnapshotHistory, MarketPulseEvent, MarketReviewReport
from app.services.market.review import MarketReviewService, build_market_review_summary, list_market_review_history


def _session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    return Session()


def test_market_review_generates_without_paper_account_and_coexists_by_slot() -> None:
    with _session() as db:
        payload = {
            "ok": True,
            "updated_at": "2026-05-25 11:30:00",
            "snapshot_count": 5200,
            "stock_up_ratio": 0.58,
            "stock_down_ratio": 0.34,
            "stock_median_change": 0.42,
            "strong_count": 320,
            "weak_count": 110,
            "market_strength_score": 18.5,
            "market_strength_text": "全市场温和修复",
            "data_quality": "fresh",
            "data_quality_text": "全 A 股小时级快照已更新",
        }
        db.add(
            MarketHourlySnapshotHistory(
                trade_date="2026-05-25",
                snapshot_bucket="202605251130",
                data_quality="fresh",
                snapshot_count=5200,
                market_strength_score=18.5,
                payload_json=json.dumps(payload, ensure_ascii=False),
            )
        )
        db.add(
            MarketPulseEvent(
                trade_date="2026-05-25",
                pulse_level="balanced",
                data_quality="fresh",
                pulse_text="盘中结构转为可观察。",
                suggested_action="只做已入池候选，控制追高。",
                payload_json=json.dumps(
                    {
                        "leader_strength_text": "龙头强度偏强",
                        "emotion_text": "情绪温度升温",
                        "market_strength_text": "市场宽度修复",
                    },
                    ensure_ascii=False,
                ),
            )
        )
        db.commit()

        service = MarketReviewService(db)
        midday = service.generate_review_report(report_slot="midday", target_date=date(2026, 5, 25))
        midday_again = service.generate_review_report(report_slot="midday", target_date=date(2026, 5, 25))
        close = service.generate_review_report(report_slot="close", target_date=date(2026, 5, 25))
        db.commit()

        rows = db.execute(select(MarketReviewReport)).scalars().all()
        assert midday.id == midday_again.id
        assert midday.id != close.id
        assert {row.report_slot for row in rows} == {"midday", "close"}
        assert "午盘市场复盘" in midday.overall_summary
        assert "收盘市场复盘" in close.overall_summary
        assert "这次统计了 5200 只股票" in midday.overall_summary
        assert "涨的面占优" in midday.overall_summary


def test_market_review_summary_empty_is_market_scoped() -> None:
    with _session() as db:
        status, reports = build_market_review_summary(db, target_date=date(2026, 5, 25))

        assert reports == []
        assert status.review_subject == "全市场"
        assert status.source_scope == "market"
        assert status.status_text == "今日暂无市场复盘"
        assert "市场复盘" in status.suggested_action


def test_market_review_history_is_not_account_scoped() -> None:
    with _session() as db:
        report = MarketReviewService(db).generate_review_report(report_slot="midday", target_date=date(2026, 5, 25))
        db.commit()

        history = list_market_review_history(db)

        assert len(history) == 1
        assert history[0].id == report.id
        assert history[0].review_subject == "全市场"


def test_market_review_prefers_latest_usable_pulse_snapshot_and_lists_missing_data() -> None:
    with _session() as db:
        db.add(
            MarketHourlySnapshotHistory(
                trade_date="2026-05-26",
                snapshot_bucket="202605261500",
                data_quality="unavailable",
                snapshot_count=0,
                market_strength_score=0.0,
                payload_json=json.dumps(
                    {
                        "ok": False,
                        "updated_at": "2026-05-26 15:04:00",
                        "snapshot_count": 0,
                        "market_strength_score": 0.0,
                        "data_quality_text": "全 A 股小时级快照暂不可用",
                    },
                    ensure_ascii=False,
                ),
            )
        )
        db.add_all(
            [
                MarketPulseEvent(
                    trade_date="2026-05-26",
                    pulse_level="defensive",
                    data_quality="partial",
                    pulse_text="数据部分缺失，市场转弱。",
                    suggested_action="仅保留高质量信号。",
                    payload_json=json.dumps(
                        {
                            "data_quality": "partial",
                            "data_quality_text": "盘中 pulse 部分可用，缺失：emotion_temperature",
                            "leader_strength_text": "龙头强度待确认",
                            "emotion_text": "情绪温度数据不足",
                            "partial_errors": [
                                {"source": "emotion_temperature", "detail": "情绪温度样本不足"}
                            ],
                            "leader_strength_summary": {"sector_count": 0, "top": []},
                            "hourly_snapshot_summary": {
                                "ok": True,
                                "updated_at": "2026-05-26 15:02:00",
                                "snapshot_count": 4992,
                                "stock_up_ratio": 0.2432,
                                "stock_down_ratio": 0.7434,
                                "stock_median_change": -1.69,
                                "strong_count": 382,
                                "weak_count": 1300,
                                "market_strength_score": -37.37,
                                "market_strength_text": "全市场明显偏弱，控制新开仓",
                                "data_quality_text": "全 A 股小时级快照已更新",
                            },
                        },
                        ensure_ascii=False,
                    ),
                ),
                MarketPulseEvent(
                    trade_date="2026-05-26",
                    pulse_level="unavailable",
                    data_quality="unavailable",
                    pulse_text="盘中数据不足，不能形成可靠结论。",
                    suggested_action="暂停新增动作，等待数据恢复。",
                    payload_json=json.dumps(
                        {
                            "data_quality": "unavailable",
                            "data_quality_text": "盘中 pulse 暂不可用",
                            "partial_errors": [
                                {"source": "emotion_temperature", "detail": "情绪温度样本不足"}
                            ],
                            "hourly_snapshot_summary": {
                                "ok": False,
                                "updated_at": "2026-05-26 15:04:00",
                                "snapshot_count": 0,
                            },
                        },
                        ensure_ascii=False,
                    ),
                ),
            ]
        )
        db.commit()

        report = MarketReviewService(db).generate_review_report(
            report_slot="close",
            target_date=date(2026, 5, 26),
        )
        metrics = json.loads(report.raw_metrics_snapshot or "{}")
        alerts = json.loads(report.risk_alerts or "[]")

        assert "这次统计了 4992 只股票" in report.overall_summary
        assert "样本不足" not in report.overall_summary
        assert metrics["snapshot_count"] == 4992
        assert metrics["data_quality"] == "partial"
        assert metrics["autofill_details"] == []
        assert {item["source"] for item in metrics["missing_data"]} == {
            "emotion_temperature",
            "sector_relative_strength",
        }
        assert any("缺少数据：情绪温度" in item["content"] for item in alerts)


def test_market_review_history_exposes_autofill_audit_fields() -> None:
    with _session() as db:
        db.add(
            MarketHourlySnapshotHistory(
                trade_date="2026-05-26",
                snapshot_bucket="202605261300",
                data_quality="fresh",
                snapshot_count=3506,
                market_strength_score=-34.23,
                payload_json=json.dumps(
                    {
                        "ok": True,
                        "updated_at": "2026-05-26 13:04:08",
                        "snapshot_count": 3506,
                        "stock_up_ratio": 0.2795,
                        "stock_down_ratio": 0.7091,
                        "stock_median_change": -1.72,
                        "strong_count": 276,
                        "weak_count": 1017,
                        "market_strength_score": -34.23,
                        "market_strength_text": "全市场偏弱，等待午后或尾盘确认",
                        "data_quality_text": "全 A 股小时级快照已更新",
                    },
                    ensure_ascii=False,
                ),
            )
        )
        db.commit()

        report = MarketReviewService(db).generate_review_report(
            report_slot="midday",
            target_date=date(2026, 5, 26),
        )
        db.commit()

        history = list_market_review_history(db)

        assert history[0].id == report.id
        assert history[0].autofill_details
        assert history[0].missing_data == []


def test_market_review_midday_ignores_late_session_snapshots() -> None:
    with _session() as db:
        for bucket, updated_at, count, up_ratio in (
            ("202605261300", "2026-05-26 13:04:00", 3506, 0.2795),
            ("202605261500", "2026-05-26 15:02:00", 4992, 0.2432),
        ):
            db.add(
                MarketHourlySnapshotHistory(
                    trade_date="2026-05-26",
                    snapshot_bucket=bucket,
                    data_quality="fresh",
                    snapshot_count=count,
                    market_strength_score=-34.23,
                    payload_json=json.dumps(
                        {
                            "ok": True,
                            "updated_at": updated_at,
                            "snapshot_count": count,
                            "stock_up_ratio": up_ratio,
                            "stock_down_ratio": 1 - up_ratio,
                            "stock_median_change": -1.72,
                            "strong_count": 276,
                            "weak_count": 1017,
                            "market_strength_score": -34.23,
                            "market_strength_text": "全市场偏弱，等待午后或尾盘确认",
                        },
                        ensure_ascii=False,
                    ),
                )
            )
        db.commit()

        midday = MarketReviewService(db).generate_review_report(
            report_slot="midday",
            target_date=date(2026, 5, 26),
        )
        close = MarketReviewService(db).generate_review_report(
            report_slot="close",
            target_date=date(2026, 5, 26),
        )

        assert "这次统计了 3506 只股票" in midday.overall_summary
        assert "这次统计了 4992 只股票" in close.overall_summary


def test_market_review_autofills_emotion_and_leader_strength_when_possible() -> None:
    with _session() as db:
        db.add(
            MarketHourlySnapshotHistory(
                trade_date="2026-05-26",
                snapshot_bucket="202605261300",
                data_quality="fresh",
                snapshot_count=3506,
                market_strength_score=-34.23,
                payload_json=json.dumps(
                    {
                        "ok": True,
                        "updated_at": "2026-05-26 13:04:08",
                        "snapshot_count": 3506,
                        "stock_up_ratio": 0.2795,
                        "stock_down_ratio": 0.7091,
                        "stock_median_change": -1.72,
                        "strong_count": 276,
                        "weak_count": 1017,
                        "market_strength_score": -34.23,
                        "market_strength_text": "全市场偏弱，等待午后或尾盘确认",
                        "data_quality_text": "全 A 股小时级快照已更新",
                    },
                    ensure_ascii=False,
                ),
            )
        )
        db.add(
            MarketPulseEvent(
                trade_date="2026-05-26",
                pulse_level="defensive",
                data_quality="partial",
                pulse_text="数据部分缺失，市场转弱。",
                suggested_action="仅保留高质量信号。",
                payload_json=json.dumps(
                    {
                        "data_quality": "partial",
                        "data_quality_text": "盘中 pulse 部分可用，缺失：emotion_temperature",
                        "leader_strength_text": "龙头强度待确认",
                        "emotion_text": "情绪温度数据不足",
                        "partial_errors": [
                            {"source": "emotion_temperature", "detail": "情绪温度样本不足"}
                        ],
                        "leader_strength_summary": {"sector_count": 0, "top": []},
                        "hourly_snapshot_summary": {
                            "ok": True,
                            "updated_at": "2026-05-26 13:04:08",
                            "snapshot_count": 3506,
                            "stock_up_ratio": 0.2795,
                            "stock_down_ratio": 0.7091,
                            "stock_median_change": -1.72,
                            "strong_count": 276,
                            "weak_count": 1017,
                            "market_strength_score": -34.23,
                            "market_strength_text": "全市场偏弱，等待午后或尾盘确认",
                            "data_quality_text": "全 A 股小时级快照已更新",
                        },
                    },
                    ensure_ascii=False,
                ),
            )
        )
        db.commit()

        report = MarketReviewService(db).generate_review_report(
            report_slot="midday",
            target_date=date(2026, 5, 26),
        )
        metrics = json.loads(report.raw_metrics_snapshot or "{}")
        alerts = json.loads(report.risk_alerts or "[]")

        assert metrics["data_quality"] == "partial"
        assert metrics["autofill_details"]
        assert any(item["source"] == "emotion_temperature" for item in metrics["autofill_details"])
        assert any(item["source"] == "sector_relative_strength" for item in metrics["autofill_details"])
        assert all("emotion_temperature" not in item.get("source", "") for item in metrics["missing_data"])
        assert any("自动补全已填入部分缺失字段" in item["content"] for item in alerts)
