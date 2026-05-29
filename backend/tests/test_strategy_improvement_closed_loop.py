from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import DailyBarSnapshot, MarketModelObservation, MinuteBarSnapshot
from app.services.paper.exit_model_schema import EXIT_MODEL_OBSERVATION_KEY
from app.services.strategy_improvement.model_shadow import exit_model_shadow_status
from app.services.strategy_improvement.constraint_policy import constraint_policy_audit
from app.services.strategy_improvement.provider_diagnostics import summarize_etf_minute_provider_report
from app.services.strategy_improvement.report import build_closed_loop_report, render_markdown
from app.services.strategy_improvement.walkforward import walk_forward_readiness


def test_closed_loop_blocks_formal_walk_forward_when_two_year_data_is_partial() -> None:
    db = _session()
    db.add(_daily("2026-04-27", "000001"))
    db.add(_daily("2026-04-28", "000001"))
    db.commit()

    report = build_closed_loop_report(db, args=_args(), existing_report=_existing_report())

    assert report["summary"]["formal_backtest_allowed"] is False
    assert report["summary"]["walk_forward_allowed"] is False
    assert report["data_coverage"]["status"] == "partial"
    assert report["data_coverage"]["coverage_pct"] == 0.0
    assert report["data_coverage"]["calendar_span_coverage_pct"] > 0.0
    assert report["data_coverage"]["full_market_trade_day_coverage_pct"] == 0.0
    assert report["data_coverage"]["missing_detail_sample"][0]["reason"] == "below_full_market_symbol_threshold"
    assert report["data_coverage"]["missing_detail_sample"][0]["missing_symbol_estimate"] > 0
    assert report["minute_coverage"]["status"] == "blocked_by_data"
    assert report["minute_coverage"]["raw_data_status"] == "empty"
    assert report["minute_coverage"]["blocked_reason"] == "no_minute_data"
    assert report["minute_coverage"]["coverage_by_symbol_sample"][0]["reason"] == "no_minute_data"
    assert report["minute_coverage"]["window_bar_count"] == 0
    gate_by_key = {item["key"]: item for item in report["gates"]}
    assert gate_by_key["daily_24m_coverage"]["status"] == "fail"
    assert gate_by_key["daily_quality"]["status"] == "pass"
    assert gate_by_key["market_metadata_coverage"]["status"] == "fail"
    assert "daily_bar_snapshots.limit_price_coverage_lt_95pct" in gate_by_key["market_metadata_coverage"]["evidence"]["gaps"]
    assert gate_by_key["etf_t0_minute_coverage"]["status"] == "fail"
    assert gate_by_key["etf_t0_minute_coverage"]["evidence"]["data_status"] == "blocked_by_data"
    assert report["data_quality"]["metadata_coverage"]["status"] == "fail"
    assert "instruments.lifecycle_coverage_lt_95pct" in report["data_quality"]["metadata_coverage"]["blocking_gaps"]


def test_closed_loop_classifies_strategy_governance_without_changing_production_params() -> None:
    db = _session()
    db.add(_daily("2026-04-28", "000001"))
    db.commit()

    report = build_closed_loop_report(db, args=_args(), existing_report=_existing_report())
    states = {item["strategy_key"]: item["governance_state"] for item in report["strategy_governance"]["items"]}

    assert states["strong"] == "positive_expectancy_candidate"
    assert states["drawdown"] == "high_return_high_drawdown"
    assert states["weak"] == "weak_strategy"
    assert states["tiny"] == "insufficient_sample"
    assert report["strategy_governance"]["production_weight_changes"] == "not_applied"


def test_closed_loop_markdown_exposes_data_and_shadow_boundaries() -> None:
    db = _session()
    db.add(_daily("2026-04-28", "000001"))
    db.commit()

    markdown = render_markdown(build_closed_loop_report(db, args=_args(), existing_report=_existing_report()))

    assert "允许正式回测：否" in markdown
    assert "生产参数自动变更：禁止" in markdown
    assert "硬止损可被覆盖：否" in markdown
    assert "日线缺口样本" in markdown
    assert "数据质量与元数据门禁" in markdown
    assert "元数据缺口样本" in markdown
    assert "daily_bar_snapshots.limit_price_coverage_lt_95pct" in markdown
    assert "ETF 分钟线缺口样本" in markdown
    assert "daily_history_backfill_runner.py" in markdown
    assert "--scope all-stock" in markdown
    assert "--resume" in markdown
    assert "backfill_etf_minute_history.py" in markdown
    assert "--scope t0-etf" in markdown
    assert "Python 保持策略、风控、回测语义和模拟盘账本真源" in markdown
    assert "随机切分：禁止" in markdown
    assert "稳定性与过拟合检查" in markdown
    assert "防未来函数门禁" in markdown
    assert "约束增强审计" in markdown
    assert "主力模型 Shadow" in markdown


def test_closed_loop_does_not_count_out_of_window_etf_minutes_as_acceptance() -> None:
    db = _session()
    db.add(_daily("2026-04-28", "000001"))
    db.add(
        MinuteBarSnapshot(
            symbol="510300",
            market="SH",
            instrument_type="etf",
            bar_period="5m",
            trade_date="2026-05-27",
            bar_timestamp="2026-05-27 09:31",
            close_price=4.0,
            source="tencent.minute",
            data_quality="fresh",
        )
    )
    db.commit()

    report = build_closed_loop_report(db, args=_args(), existing_report=_existing_report())

    assert report["minute_coverage"]["bar_count"] == 1
    assert report["minute_coverage"]["window_bar_count"] == 0
    assert report["minute_coverage"]["out_of_window_bar_count"] == 1
    assert report["minute_coverage"]["eligible_etf_minute_coverage_pct"] == 0.0
    assert report["minute_coverage"]["status"] == "blocked_by_data"
    assert report["minute_coverage"]["raw_data_status"] == "partial"
    assert report["minute_coverage"]["blocked_reason"] == "insufficient_window_trade_day_coverage"


def test_closed_loop_requires_etf_minutes_to_cover_window_trade_days() -> None:
    db = _session()
    db.add(_daily("2026-04-27", "000001"))
    db.add(_daily("2026-04-28", "000001"))
    db.add(
        MinuteBarSnapshot(
            symbol="510300",
            market="SH",
            instrument_type="etf",
            bar_period="5m",
            trade_date="2026-04-28",
            bar_timestamp="2026-04-28 09:35",
            close_price=4.0,
            source="sina.kline",
            data_quality="fresh",
        )
    )
    db.commit()

    report = build_closed_loop_report(db, args=_args(), existing_report=_existing_report())
    sample = next(item for item in report["minute_coverage"]["coverage_by_symbol_sample"] if item["symbol"] == "510300")

    assert report["minute_coverage"]["eligible_etf_with_minutes"] == 1
    assert report["minute_coverage"]["eligible_etf_with_sufficient_window_minutes"] == 0
    assert report["minute_coverage"]["eligible_etf_any_minute_coverage_pct"] > 0
    assert report["minute_coverage"]["eligible_etf_minute_coverage_pct"] == 0.0
    assert report["minute_coverage"]["status"] == "blocked_by_data"
    assert report["minute_coverage"]["raw_data_status"] == "partial"
    assert sample["trade_day_coverage_pct"] == 50.0
    assert sample["reason"] == "insufficient_window_trade_day_coverage"


def test_etf_minute_provider_diagnostics_summarizes_failures_without_credentials(tmp_path: Path) -> None:
    report_path = tmp_path / "etf-minute-backfill-tushare-probe.json"
    payload = {
        "status": "partial_data",
        "generated_at": "2026-05-28T12:00:00",
        "totals": {"ok": 0, "skip": 0, "empty": 1, "error": 0},
        "results": [
            {
                "symbol": "510300",
                "provider_errors": [
                    {"source": "tushare.stk_mins", "message": "tushare token not configured"},
                    {"source": "eastmoney.etf_minute", "message": "token=secret should not leak"},
                ],
            }
        ],
    }

    diagnostics = summarize_etf_minute_provider_report(payload, report_path)

    assert diagnostics["status"] == "partial_data"
    assert diagnostics["totals"]["ok"] == 0
    assert diagnostics["write_effect"] == "no_bars_written"
    assert diagnostics["provider_errors_sample"][0]["source"] == "tushare.stk_mins"
    assert diagnostics["provider_errors_sample"][0]["message"] == "tushare token not configured"
    assert diagnostics["provider_errors_sample"][1]["message"] == "message redacted because it may contain credentials"


def test_metadata_gate_requires_real_field_coverage_not_only_schema() -> None:
    db = _session()
    db.add(_daily("2026-04-28", "000001"))
    db.commit()

    report = build_closed_loop_report(db, args=_args(), existing_report=_existing_report())
    metadata = report["data_quality"]["metadata_coverage"]

    assert metadata["status"] == "fail"
    assert "daily_bar_snapshots.limit_up_price" not in metadata["blocking_gaps"]
    assert "daily_bar_snapshots.limit_price_coverage_lt_95pct" in metadata["blocking_gaps"]
    assert "instruments.lifecycle_coverage_lt_95pct" in metadata["blocking_gaps"]


def test_metadata_gate_requires_real_etf_intraday_execution_metadata() -> None:
    db = _session()
    db.add(_daily("2026-04-28", "000001"))
    db.add(
        MinuteBarSnapshot(
            symbol="510300",
            market="SH",
            instrument_type="etf",
            bar_period="5m",
            trade_date="2026-04-28",
            bar_timestamp="2026-04-28 09:35",
            close_price=4.0,
            source="sina.kline",
            data_quality="partial_metadata",
            bid_ask_spread=0.0,
            premium_discount_pct=None,
            tracking_index_symbol="000300",
            liquidity_tier="sufficient",
        )
    )
    db.commit()

    report = build_closed_loop_report(db, args=_args(), existing_report=_existing_report())
    metadata = report["data_quality"]["metadata_coverage"]
    check = next(item for item in metadata["data_checks"] if item["key"] == "etf_intraday_execution_metadata_coverage")

    assert check["status"] == "fail"
    assert "minute_bar_snapshots.bid_ask_spread_positive_coverage_lt_95pct" in metadata["blocking_gaps"]
    assert "minute_bar_snapshots.premium_discount_coverage_lt_95pct" in metadata["blocking_gaps"]
    assert "minute_bar_snapshots.data_quality_fresh_coverage_lt_95pct" in metadata["blocking_gaps"]
    assert check["evidence"]["tracking_index_symbol_pct"] == 100.0
    assert "etf_intraday_execution_metadata_coverage" in render_markdown(report)


def test_metadata_gate_does_not_use_30m_metadata_for_5m_acceptance() -> None:
    db = _session()
    db.add(_daily("2026-04-28", "000001"))
    db.add(
        MinuteBarSnapshot(
            symbol="510300",
            market="SH",
            instrument_type="etf",
            bar_period="30m",
            trade_date="2026-04-28",
            bar_timestamp="2026-04-28 10:00",
            close_price=4.0,
            source="sina.kline",
            data_quality="fresh",
            bid_ask_spread=0.001,
            premium_discount_pct=0.01,
            tracking_index_symbol="000300",
            liquidity_tier="sufficient",
        )
    )
    db.commit()

    report = build_closed_loop_report(db, args=_args(), existing_report=_existing_report())
    metadata = report["data_quality"]["metadata_coverage"]
    check = next(item for item in metadata["data_checks"] if item["key"] == "etf_intraday_execution_metadata_coverage")

    assert report["minute_coverage"]["bar_period"] == "5m"
    assert check["evidence"]["bar_period"] == "5m"
    assert check["evidence"]["etf_minute_rows"] == 0
    assert "minute_bar_snapshots.etf_execution_metadata_rows" in metadata["blocking_gaps"]


def test_walk_forward_readiness_builds_time_ordered_12_3_3_monthly_windows() -> None:
    trade_dates = [f"2024-{month:02d}-15" for month in range(1, 13)] + [f"2025-{month:02d}-15" for month in range(1, 9)]
    daily = {"coverage_pct": 100.0, "trade_day_count": len(trade_dates), "trade_dates": trade_dates}
    strategies = {
        "items": [
            {
                "strategy_key": "strong",
                "strategy_title": "strong",
                "governance_state": "positive_expectancy_candidate",
                "filled_count": 80,
            }
        ]
    }

    report = walk_forward_readiness(daily=daily, strategies=strategies, min_trade_days=1, min_daily_coverage_pct=95.0)

    assert report["status"] == "ready"
    assert report["random_split_allowed"] is False
    assert report["window_count"] == 3
    assert report["windows"][0]["train_start"] == "2024-01-15"
    assert report["windows"][0]["train_end"] == "2024-12-15"
    assert report["windows"][0]["validation_start"] == "2025-01-15"
    assert report["windows"][0]["validation_end"] == "2025-03-15"
    assert report["windows"][0]["oos_start"] == "2025-04-15"
    assert report["windows"][0]["oos_end"] == "2025-06-15"
    assert report["windows"][0]["split_order"] == "train_before_validation_before_oos"
    assert any(item["name"] == "min_score" and item["values"] == ["current", "+3", "+5"] for item in report["controlled_parameter_grid"])
    assert {item["key"] for item in report["stability_checks"]} >= {"pbo_or_equivalent", "deflated_sharpe_or_equivalent", "parameter_stability_pm_10pct"}


def test_temporal_guard_blocks_shadow_features_with_future_fields() -> None:
    db = _session()
    db.add(_daily("2026-04-27", "000001"))
    db.add(_daily("2026-04-28", "000001"))
    db.add(
        MarketModelObservation(
            model_key=EXIT_MODEL_OBSERVATION_KEY,
            symbol="000001",
            trade_date="2026-04-28",
            signal_state="hold->hold",
            confidence=0.8,
            payload_json='{"feature_snapshot":{"feature_values":{"pnl_pct":1.0,"future_return_5d":8.0}}}',
            outcome_status="pending",
        )
    )
    db.commit()

    report = build_closed_loop_report(db, args=_args(), existing_report=_existing_report())
    gate_by_key = {item["key"]: item for item in report["gates"]}

    assert report["temporal_guard"]["status"] == "fail"
    assert gate_by_key["temporal_no_future_function"]["status"] == "fail"
    assert "feature_values.future_return_5d" in report["temporal_guard"]["issues"][0]["forbidden_keys"]


def test_exit_model_shadow_status_reports_action_diff_and_blockers() -> None:
    db = _session()
    db.add(
        MarketModelObservation(
            model_key=EXIT_MODEL_OBSERVATION_KEY,
            symbol="000001",
            trade_date="2026-04-28",
            signal_state="hold->sell_50",
            confidence=0.8,
            payload_json='{"rule_action":"hold","model_action":"sell_50","outcome_5d":{"return_5d_pct":-1.2,"max_adverse_5d_pct":-3.0,"max_favorable_5d_pct":1.0}}',
            outcome_status="settled",
        )
    )
    db.add(
        MarketModelObservation(
            model_key=EXIT_MODEL_OBSERVATION_KEY,
            symbol="000002",
            trade_date="2026-04-28",
            signal_state="sell_70->hold",
            confidence=0.0,
            payload_json='{"rule_action":"sell_70","model_action":"hold","fallback_reason":"model_unavailable","outcome_5d":{"return_5d_pct":2.0,"max_adverse_5d_pct":-0.5,"max_favorable_5d_pct":6.0}}',
            outcome_status="settled",
        )
    )
    db.add(
        MarketModelObservation(
            model_key=EXIT_MODEL_OBSERVATION_KEY,
            symbol="000003",
            trade_date="2026-04-28",
            signal_state="hard_stop->hold",
            confidence=0.7,
            payload_json='{"rule_action":"hard_stop","model_action":"hold"}',
            outcome_status="pending",
        )
    )
    db.commit()

    shadow = exit_model_shadow_status(db)

    assert shadow["shadow_only"] is True
    assert shadow["promotion_ready"] is False
    assert shadow["action_diff"]["more_aggressive_than_rule"] == 1
    assert shadow["action_diff"]["less_aggressive_than_rule"] == 2
    assert shadow["action_diff"]["fallback"] == 1
    assert shadow["action_diff"]["hard_stop_override_risk_count"] == 1
    assert shadow["outcome_summary"]["settled_or_labeled_count"] == 2
    assert "hard_stop_override_risk_detected" in shadow["promotion_blockers"]


def test_closed_loop_includes_main_force_shadow_status() -> None:
    db = _session()
    db.add(_daily("2026-04-28", "000001"))
    db.add(
        MarketModelObservation(
            model_key="main_force_accumulation_washout_markup_v1",
            symbol="000001",
            trade_date="2026-04-28",
            signal_state="buy_probe",
            confidence=0.7,
            score=68.0,
            payload_json='{"model_advice":{"stage":"washout","action":"buy_probe","score":68.0,"confidence":0.7},"fallback_reason":null}',
            outcome_status="pending",
        )
    )
    db.commit()

    report = build_closed_loop_report(db, args=_args(), existing_report=_existing_report())

    assert report["main_force_model_shadow"]["model_key"] == "main_force_accumulation_washout_markup_v1"
    assert report["main_force_model_shadow"]["record_count"] == 1
    assert any("主力模型 Shadow" in item for item in report["next_actions"])


def test_constraint_policy_blocks_missing_constraints_and_bad_weak_action() -> None:
    strategies = {
        "items": [
            {
                "strategy_key": "weak",
                "strategy_title": "weak",
                "governance_state": "weak_strategy",
                "recommended_action": "walk_forward_then_paper_observe",
                "constraints_to_test": ["data_quality_non_fresh_no_strong_buy"],
                "parameter_grid_allowed": [{"name": "min_score", "values": ["current"]}],
            }
        ]
    }

    audit = constraint_policy_audit(strategies)

    assert audit["status"] == "fail"
    keys = {item["key"] for item in audit["issues"]}
    assert "missing_base_constraints" in keys
    assert "missing_risk_constraints" in keys
    assert "weak_strategy_not_paused" in keys


def test_closed_loop_constraint_policy_gate_passes_for_governed_report() -> None:
    db = _session()
    db.add(_daily("2026-04-28", "000001"))
    db.commit()

    report = build_closed_loop_report(db, args=_args(), existing_report=_existing_report())
    gate_by_key = {item["key"]: item for item in report["gates"]}

    assert report["constraint_policy"]["status"] == "pass"
    assert gate_by_key["constraint_policy_coverage"]["status"] == "pass"
    assert report["constraint_policy"]["production_effect"] == "audit_only_no_parameter_write"


def test_new_strategy_improvement_files_stay_under_500_lines() -> None:
    root = Path("/Users/j/Documents/gupiao")
    paths = [root / "backend/scripts/strategy_improvement_closed_loop.py", *sorted((root / "backend/app/services/strategy_improvement").glob("*.py"))]

    for path in paths:
        assert len(path.read_text(encoding="utf-8").splitlines()) <= 500, str(path)


def _session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def _daily(trade_date: str, symbol: str) -> DailyBarSnapshot:
    return DailyBarSnapshot(
        symbol=symbol,
        market="CN",
        instrument_type="stock",
        trade_date=trade_date,
        open_price=10,
        close_price=10.2,
        high_price=10.5,
        low_price=9.8,
        volume=1000,
        amount=10000,
        pct_chg=2,
    )


def _args() -> Namespace:
    return Namespace(
        start="2024-05-28",
        end="2026-04-28",
        existing_backtest="docs/reports/strategy-24m-backtest-2026-05-28.json",
        min_daily_coverage_pct=95.0,
        min_stock_symbols=4500,
        min_etf_minute_coverage_pct=85.0,
        min_wf_trade_days=360,
    )


def _existing_report() -> dict:
    return {
        "all_strategies": [
            _strategy("strong", filled=80, pf=1.6, avg=0.8, dd=-20, win=58, stop=12),
            _strategy("drawdown", filled=80, pf=1.2, avg=0.3, dd=-70, win=48, stop=28),
            _strategy("weak", filled=80, pf=0.8, avg=-0.2, dd=-30, win=42, stop=35),
            _strategy("tiny", filled=8, pf=2.0, avg=1.2, dd=-5, win=75, stop=0),
        ],
        "inventory": {"implemented_strategy_groups": []},
    }


def _strategy(key: str, *, filled: int, pf: float, avg: float, dd: float, win: float, stop: float) -> dict:
    return {
        "strategy_key": key,
        "strategy_title": key,
        "strategy_family": "test",
        "sample_count": filled,
        "filled_count": filled,
        "profit_factor": pf,
        "avg_trade_return_pct": avg,
        "max_drawdown_pct": dd,
        "win_rate_pct": win,
        "stop_loss_rate_pct": stop,
    }
