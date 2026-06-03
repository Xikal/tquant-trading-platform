from __future__ import annotations

from datetime import date

from app.models.entities import SystemSetting
from app.services.shared.feature_flags import clear_feature_flag_cache
from app.services.trading_experience.limit_up_followthrough import build_backtest_report, build_items, persist_backtest_report
from app.services.trading_experience.service import TradingExperienceService
from backend.tests.trading_experience_fixtures import seed_daily_bars, seed_limit_up_backtest_bars, session_factory


def test_limit_up_followthrough_blocks_without_backtest_gate() -> None:
    Session = session_factory()
    db = Session()
    seed_daily_bars(db, pct=9.8)

    items = build_items(db, trade_date=date(2026, 5, 27), limit=10)

    assert items
    assert items[0].status == "blocked"
    assert items[0].data_quality == "blocked"
    assert items[0].sample_count == 0


def test_limit_up_followthrough_response_exposes_blocked_backtest_gate() -> None:
    Session = session_factory()
    db = Session()
    db.add(SystemSetting(key="ff_trading_experience_suite_enabled", value="true"))
    db.add(SystemSetting(key="ff_limit_up_followthrough_enabled", value="true"))
    db.commit()
    clear_feature_flag_cache()
    seed_daily_bars(db, pct=9.8)

    response = TradingExperienceService(db).limit_up_followthrough(trade_date=date(2026, 5, 27), limit=10)

    assert response.enabled is True
    assert response.data_quality == "blocked"
    assert response.backtest_gate == "blocked"
    assert response.gate_reasons == ["24m_backtest_not_available"]


def test_limit_up_backtest_blocks_when_daily_bars_are_less_than_24m() -> None:
    Session = session_factory()
    db = Session()
    seed_daily_bars(db, pct=9.8)

    report = build_backtest_report(db, end_date=date(2026, 5, 27))

    assert report["backtest_gate"] == "blocked"
    assert report["data_quality"] == "blocked"
    assert "insufficient_24m_daily_bars" in report["gate_reasons"]


def test_limit_up_backtest_passes_with_stable_24m_samples_and_no_future_leak() -> None:
    Session = session_factory()
    db = Session()
    seed_limit_up_backtest_bars(db, positive=True)

    report = build_backtest_report(db, end_date=date(2026, 5, 31))

    assert report["backtest_gate"] == "passed"
    assert report["overall"]["sample_count"] >= 30
    assert report["overall"]["profit_factor"] >= 1.2
    assert report["future_leak_check"]["status"] == "passed"
    sample = _first_sample(report)
    assert sample["outcome_start_date"] > sample["confirmation_date"]
    assert "production_score" not in report


def test_limit_up_backtest_fails_with_negative_24m_samples() -> None:
    Session = session_factory()
    db = Session()
    seed_limit_up_backtest_bars(db, positive=False)

    report = build_backtest_report(db, end_date=date(2026, 5, 31))

    assert report["backtest_gate"] == "failed"
    assert "profit_factor_below_threshold" in report["gate_reasons"]


def test_limit_up_followthrough_reads_cached_backtest_snapshot() -> None:
    Session = session_factory()
    db = Session()
    db.add(SystemSetting(key="ff_trading_experience_suite_enabled", value="true"))
    db.add(SystemSetting(key="ff_limit_up_followthrough_enabled", value="true"))
    db.commit()
    clear_feature_flag_cache()
    seed_limit_up_backtest_bars(db, positive=True)
    report = build_backtest_report(db, end_date=date(2026, 5, 31))
    persist_backtest_report(db, report)

    response = TradingExperienceService(db).limit_up_followthrough(trade_date=date(2026, 5, 31), limit=10)

    assert response.backtest_gate == "passed"
    assert response.data_quality == "ok"
    assert response.source == "trading_experience_snapshots"


def _first_sample(report: dict) -> dict:
    for metrics in report["patterns"].values():
        samples = metrics.get("samples") or []
        if samples:
            return samples[0]
    raise AssertionError("expected backtest samples")
