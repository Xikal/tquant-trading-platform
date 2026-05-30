from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "backend"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.core.database import SessionLocal, init_db
from app.models.entities import DailyBarSnapshot
from app.services.low_buy.execution_simulation import ROUND_TRIP_COST_BPS
from app.services.low_buy.execution_simulation import ExecutionSimulationOverride
from app.services.low_buy.front_row_filter import FrontRowFilterConfig
from app.services.low_buy.production_scoring_config import (
    PORTFOLIO_CANDIDATE_SCORE_THRESHOLD,
    PRODUCTION_SCORING_CONFIG_VERSION,
    SHADOW_CONFIRM_SCORE_THRESHOLD,
)
from app.services.low_buy_screener import PLAYBOOKS, LowBuyScreenerService
from app.services.low_buy.strategy_families import resolve_strategy_family, resolve_strategy_family_label

try:
    from .low_buy_market_backtest import _count_signal_state, _load_a_share_universe_count
    from .low_buy_market_backtest_reporting import (
        CONFIRMED_STATES,
        EVALUATED_STATES,
        StrategyBacktestStats,
        backtest_performance_metrics,
        history_window_days,
        portfolio_backtest_metrics,
    )
    from .low_buy_market_backtest_runner import run_fast_isolated_execution_matrix_backtest
    from .strategy_24m_front_row_filter import front_row_filter_ab_summary
except ImportError:
    from low_buy_market_backtest import _count_signal_state, _load_a_share_universe_count
    from low_buy_market_backtest_reporting import (
        CONFIRMED_STATES,
        EVALUATED_STATES,
        StrategyBacktestStats,
        backtest_performance_metrics,
        history_window_days,
        portfolio_backtest_metrics,
    )
    from low_buy_market_backtest_runner import run_fast_isolated_execution_matrix_backtest
    from strategy_24m_front_row_filter import front_row_filter_ab_summary


DEFAULT_START = "2024-05-28"
DEFAULT_JSON_OUTPUT = ROOT_DIR / "docs" / "reports" / "front-row-weighted-production-scoring-backtest-2026-05-29.json"
DEFAULT_MD_OUTPUT = ROOT_DIR / "docs" / "reports" / "front-row-weighted-production-scoring-backtest-2026-05-29.md"
VARIANTS = (
    "baseline",
    "front_row_only",
    "front_row_weighted_shadow",
    "front_row_weighted_max5",
    "front_row_weighted_max10",
)
DISPLAY_VARIANTS = (
    "baseline",
    "front_row_only",
    "front_row_weighted_shadow",
    "front_row_weighted",
)
WEIGHTED_VARIANTS = {"front_row_weighted_max5", "front_row_weighted_max10"}
EXTRA_COST_BPS_SCENARIOS = (0.0, 10.0, 30.0, 50.0)
GOOD_MARKET_STATES = {"broad_rally", "repair", "weight_support", "weight_support_active"}
WEAK_MARKET_STATES = {"low_volume_wait", "fast_rotation"}
RETREAT_MARKET_STATES = {"high_flyer_retreat", "risk_release", "panic"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="前排加权生产评分 Shadow/Paper 组合回测")
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default="")
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MD_OUTPUT))
    parser.add_argument("--scan-limit", type=int, default=480)
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--forward-days", type=int, default=5)
    parser.add_argument("--months", type=int, default=24)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    init_db()
    output_json = Path(args.json_output)
    output_md = Path(args.markdown_output)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        report = _run_report(db, args)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"json": str(output_json), "markdown": str(output_md), "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 0


def _run_report(db, args: argparse.Namespace) -> dict[str, Any]:
    service = LowBuyScreenerService()
    source = _data_source_summary(db)
    trade_dates = service._get_recent_trade_dates(max(760, args.months * 31 + args.forward_days + 80))
    latest_available = source.get("daily_max_trade_date", "")
    requested_end = args.end or latest_available
    latest_completed = min(service._resolve_latest_completed_trade_date(trade_dates), requested_end)
    evaluation_dates = _evaluation_dates_local(
        trade_dates=trade_dates,
        start=args.start,
        latest_completed=latest_completed,
        forward_days=args.forward_days,
        end=requested_end,
    )
    strategy_keys = list(PLAYBOOKS.keys())
    stats_by_variant = {variant: _initial_stats(strategy_keys) for variant in VARIANTS}
    execution_overrides = {variant: ExecutionSimulationOverride(enforce_t1_exit_rules=True) for variant in VARIANTS}
    run_fast_isolated_execution_matrix_backtest(
        db=db,
        service=service,
        stats_by_variant=stats_by_variant,
        trade_dates=trade_dates,
        evaluation_dates=evaluation_dates,
        latest_completed=latest_completed,
        strategy_keys=strategy_keys,
        evaluated_states=set(EVALUATED_STATES),
        execution_overrides=execution_overrides,
        market_guard=None,
        scan_limit=args.scan_limit,
        limit=args.limit,
        forward_days=args.forward_days,
        history_window_days_value=history_window_days(args.months, args.forward_days),
        count_signal_state=_count_signal_state,
        front_row_filters={"front_row_only": FrontRowFilterConfig(enabled=True)},
        production_score_sort_variants={
            "front_row_weighted_max5",
            "front_row_weighted_max10",
        },
    )
    variants = {
        key: _variant_summary(key, stats_by_variant[key])
        for key in VARIANTS
    }
    display_variants = _display_variants(variants)
    return {
        "title": "前排加权生产评分 Shadow/Paper 组合回测",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "scope": {
            "requested_start": args.start,
            "requested_end": requested_end,
            "actual_evaluation_start": evaluation_dates[0] if evaluation_dates else "",
            "actual_evaluation_end": evaluation_dates[-1] if evaluation_dates else "",
            "evaluation_trade_days": len(evaluation_dates),
            "strategy_count": len(strategy_keys),
            "strategy_keys": strategy_keys,
        },
        "data_source": source,
        "config": {
            "production_scoring_config_version": PRODUCTION_SCORING_CONFIG_VERSION,
            "front_row_only_is_production_allowed": False,
            "shadow_first": True,
            "production_sort_replaced": False,
            "allowed_production_signal_states": sorted(CONFIRMED_STATES),
            "watch_only_signal_states": ["near_entry", "observe_confirmed", "watch", "avoid"],
            "portfolio_constraints": {
                "max_positions": [5, 10],
                "capital_occupied_during_holding": True,
                "same_symbol_reentry_blocked": True,
                "max_daily_per_strategy": 2,
                "max_per_sector": 2,
                "weak_market_total_position_cap_pct": 40.0,
                "retreat_market_new_position_blocked": True,
                "production_score_min_for_paper_candidate": SHADOW_CONFIRM_SCORE_THRESHOLD,
                "portfolio_candidate_score_threshold": PORTFOLIO_CANDIDATE_SCORE_THRESHOLD,
            },
        },
        "summary": _overall_summary(variants),
        "variants": variants,
        "display_variants": display_variants,
        "display_variant_order": list(DISPLAY_VARIANTS),
        "front_row_filter": front_row_filter_ab_summary(
            baseline_stats=stats_by_variant["baseline"],
            front_row_stats=stats_by_variant["front_row_only"],
            config=FrontRowFilterConfig(enabled=True),
        ),
        "comparisons": _comparisons(variants),
        "signal_state_breakdown": {
            key: _breakdown(_all_outcomes(stats_by_variant[key]), lambda item: item.buy_signal_state or "unknown")
            for key in VARIANTS
        },
        "front_row_tier_breakdown": {
            key: _breakdown(_all_outcomes(stats_by_variant[key]), lambda item: item.front_row_tier or "unknown", states=set(CONFIRMED_STATES))
            for key in VARIANTS
        },
        "quarter_breakdown": {
            key: _breakdown(_all_outcomes(stats_by_variant[key]), lambda item: _quarter(item.signal_date), states=set(CONFIRMED_STATES))
            for key in VARIANTS
        },
        "market_adaptive_density": _market_adaptive_density(
            variants=variants,
            evaluation_trade_days=len(evaluation_dates),
        ),
        "no_signal_intervals": {
            key: _no_signal_intervals(_all_outcomes(stats_by_variant[key]), evaluation_dates=evaluation_dates)
            for key in VARIANTS
        },
        "precision_gate": _precision_gate(variants, evaluation_dates=evaluation_dates),
        "time_series_splits": _time_series_splits(variants, evaluation_dates=evaluation_dates),
        "anti_future_function_audit": _anti_future_function_audit(variants),
        "anti_overfit_policy": {
            "random_split_allowed": False,
            "split_order": "train_before_validation_before_oos",
            "train": "2024Q3-2025Q4",
            "validation": "2026Q1",
            "oos": "2026Q2",
            "note": "本次权重来自固定开发文档，报告只按时间顺序验收，不根据 OOS 结果反向调参。",
        },
        "decision": _decision(variants, evaluation_dates=evaluation_dates),
    }


def _initial_stats(strategy_keys: list[str]) -> dict[str, StrategyBacktestStats]:
    return {
        strategy: StrategyBacktestStats(
            strategy_key=strategy,
            strategy_title=PLAYBOOKS[strategy]["title"],
            strategy_family=resolve_strategy_family(strategy),
            strategy_family_text=resolve_strategy_family_label(strategy),
        )
        for strategy in strategy_keys
    }


def _variant_summary(variant: str, stats: dict[str, StrategyBacktestStats]) -> dict[str, Any]:
    outcomes = _all_outcomes(stats)
    confirmed = [item for item in outcomes if item.buy_signal_state in CONFIRMED_STATES]
    metrics = backtest_performance_metrics(outcomes, states=set(CONFIRMED_STATES))
    portfolio5 = portfolio_backtest_metrics(
        confirmed,
        max_positions=5,
        sort_by_production_score=variant in WEIGHTED_VARIANTS,
    )
    portfolio10 = portfolio_backtest_metrics(
        confirmed,
        max_positions=10,
        sort_by_production_score=variant in WEIGHTED_VARIANTS,
    )
    cost_stress = _cost_stress_metrics(confirmed, sort_by_production_score=variant in WEIGHTED_VARIANTS)
    production_scored = [item for item in confirmed if item.production_score is not None]
    near_entry = [item for item in outcomes if item.buy_signal_state == "near_entry"]
    return {
        "variant": variant,
        "sample_count": len(confirmed),
        "filled_count": len([item for item in confirmed if item.execution_status == "filled"]),
        "all_evaluated_sample_count": len(outcomes),
        "near_entry_sample_count": len(near_entry),
        "near_entry_production_score_count": len([item for item in near_entry if item.production_score is not None]),
        "production_scored_count": len(production_scored),
        "production_score_sort_enabled": variant in WEIGHTED_VARIANTS,
        "daily_signal_equal_weight_compound_return_pct": metrics["daily_signal_equal_weight_compound_return_pct"],
        "real_portfolio_max5_return_pct": portfolio5["portfolio_return_pct"],
        "real_portfolio_max10_return_pct": portfolio10["portfolio_return_pct"],
        "max_drawdown_pct": metrics["max_drawdown_pct"],
        "sharpe_ratio": metrics["sharpe_ratio"],
        "win_rate_pct": metrics["win_rate_pct"],
        "profit_factor": metrics["profit_factor"],
        "avg_trade_return_pct": metrics["avg_net_return_pct"],
        "avg_holding_days": metrics["avg_holding_days"],
        "signal_days": metrics["signal_days"],
        "longest_no_signal_days": _longest_no_signal_days(confirmed),
        "portfolio_max5": portfolio5,
        "portfolio_max10": portfolio10,
        "cost_stress": cost_stress,
        "tradability_proxy": _tradability_proxy(confirmed),
        "field_asof_audit": _field_asof_audit(outcomes),
        "skip_reason_counts": _merge_counts(
            portfolio5.get("skip_reason_counts", {}),
            portfolio10.get("skip_reason_counts", {}),
        ),
        "strategy_diagnostics": {
            "front_row_filter_count": sum(item.front_row_filter_count for item in stats.values()),
            "front_row_filter_counts": _merge_counts(*(item.front_row_filter_counts for item in stats.values())),
            "skipped_by_state_counts": _merge_counts(*(item.skipped_by_state_counts for item in stats.values())),
            "pending_reason_counts": _merge_counts(*(item.pending_reason_counts for item in stats.values())),
        },
        "by_signal_state": _breakdown(outcomes, lambda item: item.buy_signal_state or "unknown"),
        "by_strategy": _breakdown(confirmed, lambda item: item.strategy_key or "unknown"),
        "by_front_row_tier": _breakdown(confirmed, lambda item: item.front_row_tier or "unknown"),
        "by_market_state": _breakdown(confirmed, lambda item: item.market_state or "unknown"),
        "by_quarter": _breakdown(confirmed, lambda item: _quarter(item.signal_date)),
        "outcome_rows": _outcome_rows(confirmed),
    }


def _comparisons(variants: dict[str, dict[str, Any]]) -> dict[str, Any]:
    baseline = variants["baseline"]
    return {
        key: _delta(baseline, value)
        for key, value in variants.items()
        if key != "baseline"
    }


def _display_variants(variants: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = {
        "baseline": variants["baseline"],
        "front_row_only": variants["front_row_only"],
        "front_row_weighted_shadow": variants["front_row_weighted_shadow"],
        "front_row_weighted": variants["front_row_weighted_max5"],
    }
    return {
        key: {
            "source_variant": value["variant"],
            "sample_count": value["sample_count"],
            "filled_count": value["filled_count"],
            "signal_days": value["signal_days"],
            "longest_no_signal_days": value["longest_no_signal_days"],
            "signal_quality": {
                "daily_signal_equal_weight_compound_return_pct": value["daily_signal_equal_weight_compound_return_pct"],
                "max_drawdown_pct": value["max_drawdown_pct"],
                "profit_factor": value["profit_factor"],
                "avg_trade_return_pct": value["avg_trade_return_pct"],
            },
            "real_portfolio": {
                "max5": _portfolio_display(value["portfolio_max5"]),
                "max10": _portfolio_display(value["portfolio_max10"]),
            },
            "tradability_proxy": value.get("tradability_proxy", {}),
            "field_asof_audit": value.get("field_asof_audit", {}),
        }
        for key, value in rows.items()
    }


def _portfolio_display(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "return_pct": item["portfolio_return_pct"],
        "annualized_return_pct": item["annualized_return_pct"],
        "max_drawdown_pct": item["max_drawdown_pct"],
        "profit_factor": item["profit_factor"],
        "win_rate_pct": item["win_rate_pct"],
        "avg_trade_return_pct": item["avg_trade_return_pct"],
        "avg_capital_utilization_pct": item["avg_capital_utilization_pct"],
        "trade_count": item["trade_count"],
        "skipped_count": item["skipped_count"],
        "max_concurrent_positions": item["max_concurrent_positions"],
        "concentration": item.get("concentration", {}),
    }


def _delta(baseline: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    return {
        "sample_retention_rate_pct": _pct(variant["sample_count"], baseline["sample_count"]),
        "filled_retention_rate_pct": _pct(variant["filled_count"], baseline["filled_count"]),
        "signal_day_retention_rate_pct": _pct(variant["signal_days"], baseline["signal_days"]),
        "daily_signal_equal_weight_compound_return_pct_delta": round(
            float(variant["daily_signal_equal_weight_compound_return_pct"]) - float(baseline["daily_signal_equal_weight_compound_return_pct"]),
            4,
        ),
        "real_portfolio_max5_return_pct_delta": round(
            float(variant["real_portfolio_max5_return_pct"]) - float(baseline["real_portfolio_max5_return_pct"]),
            4,
        ),
        "real_portfolio_max10_return_pct_delta": round(
            float(variant["real_portfolio_max10_return_pct"]) - float(baseline["real_portfolio_max10_return_pct"]),
            4,
        ),
        "max_drawdown_reduction_pct": round(
            abs(float(baseline["max_drawdown_pct"])) - abs(float(variant["max_drawdown_pct"])),
            4,
        ),
        "profit_factor_delta": round(float(variant["profit_factor"]) - float(baseline["profit_factor"]), 4),
        "avg_trade_return_pct_delta": round(float(variant["avg_trade_return_pct"]) - float(baseline["avg_trade_return_pct"]), 4),
        "longest_no_signal_days_delta": int(variant["longest_no_signal_days"]) - int(baseline["longest_no_signal_days"]),
    }


def _overall_summary(variants: dict[str, dict[str, Any]]) -> dict[str, Any]:
    baseline = variants["baseline"]
    max5 = variants["front_row_weighted_max5"]
    max10 = variants["front_row_weighted_max10"]
    return {
        "baseline_daily_signal_equal_weight_compound_return_pct": baseline["daily_signal_equal_weight_compound_return_pct"],
        "front_row_weighted_max5_real_portfolio_return_pct": max5["real_portfolio_max5_return_pct"],
        "front_row_weighted_max10_real_portfolio_return_pct": max10["real_portfolio_max10_return_pct"],
        "baseline_real_portfolio_max5_return_pct": baseline["real_portfolio_max5_return_pct"],
        "baseline_real_portfolio_max10_return_pct": baseline["real_portfolio_max10_return_pct"],
        "near_entry_production_score_count": sum(item["near_entry_production_score_count"] for item in variants.values()),
        "production_sort_replaced": False,
    }


def _decision(variants: dict[str, dict[str, Any]], *, evaluation_dates: list[str] | None = None) -> dict[str, Any]:
    comparisons = _comparisons(variants)
    max5_delta = comparisons["front_row_weighted_max5"]["real_portfolio_max5_return_pct_delta"]
    max10_delta = comparisons["front_row_weighted_max10"]["real_portfolio_max10_return_pct_delta"]
    max5 = variants["front_row_weighted_max5"]
    baseline = variants["baseline"]
    blockers: list[str] = []
    warnings: list[str] = []
    if max5_delta <= 0:
        blockers.append("max5_real_portfolio_not_better_than_baseline")
    if max10_delta <= 0:
        blockers.append("max10_real_portfolio_not_better_than_baseline")
    if max5["portfolio_max5"]["profit_factor"] < baseline["portfolio_max5"]["profit_factor"]:
        blockers.append("max5_portfolio_profit_factor_below_baseline")
    if abs(max5["portfolio_max5"]["max_drawdown_pct"]) > abs(baseline["portfolio_max5"]["max_drawdown_pct"]):
        blockers.append("max5_portfolio_drawdown_worse_than_baseline")
    oos_summary = _oos_window_summary(max5, evaluation_dates=evaluation_dates or [], quarters={"2026Q2"})
    if int(oos_summary["oos_window_trade_days"]) < 60:
        blockers.append("oos_window_below_60_trade_days")
    if int(oos_summary["oos_filled_count"]) < 150:
        blockers.append("oos_filled_count_below_150")
    if not _cost_gate_passed(max5):
        blockers.append("cost_adjusted_precision_gate_failed")
    if not _tradability_gate_passed(max5):
        blockers.append("tradability_proxy_requires_manual_review")
    if not _concentration_gate_passed(max5):
        blockers.append("concentration_risk_requires_review")
    if comparisons["front_row_weighted_max5"]["signal_day_retention_rate_pct"] < 75.0:
        warnings.append("signal_day_retention_below_75pct_precision_mode_warning_only")
    near_entry_errors = sum(item["near_entry_production_score_count"] for item in variants.values())
    if near_entry_errors:
        blockers.append("near_entry_misclassified_into_production")
    return {
        "recommend_small_traffic_observation": not blockers,
        "status": "shadow_paper_candidate" if not blockers else "shadow_paper_not_ready",
        "blockers": blockers,
        "warnings": warnings,
        "decision_policy": "precision_first_market_adaptive_density",
        "deprecated_blockers": ["signal_day_retention_below_75pct"],
        "notes": [
            "本次未部署上线，未替换生产排序。",
            "front_row_only 只保留为对照，不建议生产硬过滤。",
            "near_entry 只用于观察池，不进入生产收益排行。",
            "信号日留存低在精准优先准则下不再作为独立阻断项，需用成本后精准度、行情自适应密度、OOS 与可成交性替代验收。",
        ],
        "oos_gate": oos_summary,
    }


def _cost_gate_passed(variant: dict[str, Any]) -> bool:
    stressed = variant.get("cost_stress", {}).get("extra_cost_30bps", {})
    max5 = stressed.get("max5", {})
    max10 = stressed.get("max10", {})
    return (
        float(max5.get("profit_factor") or 0.0) >= 1.5
        and float(max10.get("profit_factor") or 0.0) >= 1.5
        and float(max5.get("avg_trade_return_pct") or 0.0) >= 0.5
        and float(max10.get("avg_trade_return_pct") or 0.0) >= 0.5
    )


def _tradability_gate_passed(variant: dict[str, Any]) -> bool:
    proxy = variant.get("tradability_proxy", {})
    locked = float(proxy.get("t1_locked_limit_up_rate_pct") or 0.0)
    gap = float(proxy.get("t1_open_gap_above_entry_zone_rate_pct") or 0.0)
    return locked <= 5.0 and gap <= 30.0


def _concentration_gate_passed(variant: dict[str, Any]) -> bool:
    concentration = variant.get("portfolio_max5", {}).get("concentration", {})
    top_10 = float(concentration.get("top_10_positive_trade_contribution_pct") or 0.0)
    max_symbol = float(concentration.get("max_symbol_positive_contribution_pct") or 0.0)
    return top_10 <= 50.0 and max_symbol <= 20.0


def _anti_future_function_audit(variants: dict[str, dict[str, Any]]) -> dict[str, Any]:
    violations = []
    for variant_name, variant in variants.items():
        for row in variant.get("by_signal_state", []):
            if row["key"] == "near_entry" and variants[variant_name]["near_entry_production_score_count"]:
                violations.append(f"{variant_name}:near_entry_has_production_score")
        field_audit = variant.get("field_asof_audit", {})
        if field_audit and field_audit.get("violation_count"):
            violations.append(f"{variant_name}:field_asof_violation")
    return {
        "future_leak_check": "passed" if not violations else "failed",
        "violations": violations,
        "policy": {
            "front_row_strength_data_cutoff": "signal_day_or_before",
            "market_state_data_cutoff": "signal_day_or_before",
            "sector_heat_data_cutoff": "signal_day_or_before",
            "return_start_after_signal": True,
            "random_split_allowed": False,
        },
        "field_level_audit": {
            key: value.get("field_asof_audit", {})
            for key, value in variants.items()
        },
    }


def _time_series_splits(variants: dict[str, dict[str, Any]], *, evaluation_dates: list[str]) -> dict[str, Any]:
    oos_summary = _oos_window_summary(variants["front_row_weighted_max5"], evaluation_dates=evaluation_dates, quarters={"2026Q2"})
    return {
        "split_order": "time_ordered",
        "random_split_allowed": False,
        "train": {
            "quarters": ["2024Q3", "2024Q4", "2025Q1", "2025Q2", "2025Q3", "2025Q4"],
            "weighted_summary": _quarter_subset_summary(variants["front_row_weighted_max5"], {"2024Q3", "2024Q4", "2025Q1", "2025Q2", "2025Q3", "2025Q4"}),
        },
        "validation": {
            "quarters": ["2026Q1"],
            "weighted_summary": _quarter_subset_summary(variants["front_row_weighted_max5"], {"2026Q1"}),
        },
        "oos": {
            "quarters": ["2026Q2"],
            "weighted_summary": oos_summary,
            "minimum_trade_days_required": 60,
            "minimum_oos_trade_days_required": 60,
            "minimum_oos_filled_count_required": 150,
            "status": "insufficient_oos_window" if int(oos_summary["oos_window_trade_days"]) < 60 else "sufficient",
        },
        "variant_quarter_breakdowns": {
            key: value.get("by_quarter", [])
            for key, value in variants.items()
        },
    }


def _quarter_subset_summary(variant: dict[str, Any], quarters: set[str]) -> dict[str, Any]:
    rows = [row for row in variant.get("by_quarter", []) if str(row.get("key")) in quarters]
    return {
        "sample_count": sum(int(row.get("sample_count") or 0) for row in rows),
        "filled_count": sum(int(row.get("filled_count") or 0) for row in rows),
        "signal_days": sum(int(row.get("signal_days") or 0) for row in rows),
        "quarters_present": [str(row.get("key")) for row in rows],
        "profit_factor_avg": round(sum(float(row.get("profit_factor") or 0.0) for row in rows) / max(len(rows), 1), 4),
        "avg_trade_return_pct_avg": round(sum(float(row.get("avg_trade_return_pct") or 0.0) for row in rows) / max(len(rows), 1), 4),
    }


def _oos_window_summary(variant: dict[str, Any], *, evaluation_dates: list[str], quarters: set[str]) -> dict[str, Any]:
    quarter_summary = _quarter_subset_summary(variant, quarters)
    oos_trade_dates = [trade_date for trade_date in evaluation_dates if _quarter(trade_date) in quarters]
    signal_days = int(quarter_summary["signal_days"])
    trade_days = len(oos_trade_dates)
    sample_count = int(quarter_summary["sample_count"])
    filled_count = int(quarter_summary["filled_count"])
    if not evaluation_dates:
        trade_days = int(quarter_summary.get("oos_window_trade_days") or quarter_summary.get("signal_days") or 0)
    status = "sufficient" if trade_days >= 60 and filled_count >= 150 else "insufficient_oos_window"
    return {
        **quarter_summary,
        "oos_window_trade_days": trade_days,
        "oos_signal_days": signal_days,
        "oos_sample_count": sample_count,
        "oos_filled_count": filled_count,
        "oos_signal_density_pct": _pct(signal_days, trade_days),
        "minimum_oos_trade_days_required": 60,
        "minimum_oos_filled_count_required": 150,
        "status": status,
        "note": "OOS trading days count all completed trade dates in the OOS window; signal days count only dates with candidates.",
    }


def _outcome_rows(outcomes: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in outcomes:
        rows.append(
            {
                "symbol": item.symbol,
                "name": item.name,
                "signal_date": item.signal_date,
                "strategy_key": item.strategy_key,
                "buy_signal_state": item.buy_signal_state,
                "entry_price": item.entry_price,
                "entry_zone_low": item.entry_zone_low,
                "entry_zone_high": item.entry_zone_high,
                "entry_trade_date": item.entry_trade_date,
                "exit_trade_date": item.exit_trade_date,
                "execution_status": item.execution_status,
                "net_return_pct": item.net_return_pct,
                "execution_exit_reason": item.execution_exit_reason,
                "market_state": item.market_state,
                "sector_name": item.sector_name,
                "front_row_tier": item.front_row_tier,
                "production_score": item.production_score,
                "watch_score": item.watch_score,
                "production_decision": item.production_decision,
                "warning_tags": list(item.warning_tags or []),
                "exclusion_reasons": list(item.exclusion_reasons or []),
                "t1_locked_limit_up": bool(getattr(item, "t1_locked_limit_up", False)),
                "t1_open_return_pct": float(getattr(item, "t1_open_return_pct", 0.0) or 0.0),
            }
        )
    return rows


def _breakdown(outcomes: list[Any], key_fn, states: set[str] | None = None) -> list[dict[str, Any]]:
    grouped: dict[str, list[Any]] = {}
    for item in outcomes:
        if states is not None and item.buy_signal_state not in states:
            continue
        grouped.setdefault(str(key_fn(item) or "unknown"), []).append(item)
    rows = []
    for key, items in sorted(grouped.items()):
        metrics = backtest_performance_metrics(items, states=None)
        filled = [item for item in items if item.execution_status == "filled"]
        rows.append(
            {
                "key": key,
                "sample_count": len(items),
                "filled_count": len(filled),
                "signal_days": metrics["signal_days"],
                "daily_signal_equal_weight_compound_return_pct": metrics["daily_signal_equal_weight_compound_return_pct"],
                "real_portfolio_max5_return_pct": portfolio_backtest_metrics(items, max_positions=5)["portfolio_return_pct"],
                "max_drawdown_pct": metrics["max_drawdown_pct"],
                "profit_factor": metrics["profit_factor"],
                "win_rate_pct": metrics["win_rate_pct"],
                "avg_trade_return_pct": metrics["avg_net_return_pct"],
                "avg_holding_days": metrics["avg_holding_days"],
            }
        )
    return rows


def _all_outcomes(stats: dict[str, StrategyBacktestStats]) -> list[Any]:
    return [outcome for stat in stats.values() for outcome in stat.outcomes]


def _cost_stress_metrics(outcomes: list[Any], *, sort_by_production_score: bool) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for extra_bps in EXTRA_COST_BPS_SCENARIOS:
        key = f"extra_cost_{int(extra_bps)}bps"
        max5 = portfolio_backtest_metrics(
            outcomes,
            max_positions=5,
            sort_by_production_score=sort_by_production_score,
            extra_cost_bps=extra_bps,
        )
        max10 = portfolio_backtest_metrics(
            outcomes,
            max_positions=10,
            sort_by_production_score=sort_by_production_score,
            extra_cost_bps=extra_bps,
        )
        result[key] = {
            "extra_cost_bps": extra_bps,
            "total_cost_bps_assumption": ROUND_TRIP_COST_BPS + extra_bps,
            "max5": _portfolio_display(max5),
            "max10": _portfolio_display(max10),
        }
    return result


def _tradability_proxy(outcomes: list[Any]) -> dict[str, Any]:
    filled = [item for item in outcomes if item.execution_status == "filled"]
    locked = [item for item in filled if bool(getattr(item, "t1_locked_limit_up", False))]
    gap_above_entry = [
        item
        for item in filled
        if float(getattr(item, "entry_zone_high", 0.0) or 0.0) > 0.0
        and float(getattr(item, "entry_price", 0.0) or 0.0) > 0.0
        and float(getattr(item, "t1_open_return_pct", 0.0) or 0.0)
        > (float(getattr(item, "entry_zone_high", 0.0) or 0.0) / max(float(getattr(item, "entry_price", 0.0) or 0.0), 0.01) - 1.0) * 100.0
    ]
    t1_open_returns = [float(getattr(item, "t1_open_return_pct", 0.0) or 0.0) for item in filled]
    return {
        "filled_count": len(filled),
        "t1_locked_limit_up_count": len(locked),
        "t1_locked_limit_up_rate_pct": _pct(len(locked), len(filled)),
        "t1_open_gap_above_entry_zone_proxy_count": len(gap_above_entry),
        "t1_open_gap_above_entry_zone_rate_pct": _pct(len(gap_above_entry), len(filled)),
        "avg_t1_open_return_pct": round(sum(t1_open_returns) / len(t1_open_returns), 4) if t1_open_returns else 0.0,
        "note": "涨停锁死和开盘跳空为日线代理指标，用于提示可成交性风险，不能替代逐笔盘口验证。",
    }


def _field_asof_audit(outcomes: list[Any]) -> dict[str, Any]:
    fields = ("front_row_tier", "market_state", "sector_name", "score_components", "warning_tags")
    counts = {field: 0 for field in fields}
    violations: list[str] = []
    audited = 0
    for item in outcomes:
        signal_ts = str(getattr(item, "signal_generated_at", "") or getattr(item, "signal_date", "") or "")
        data_cutoff = str(getattr(item, "data_cutoff_time", "") or "")
        return_start = str(getattr(item, "return_start_time", "") or "")
        if data_cutoff and signal_ts and data_cutoff > signal_ts:
            violations.append(f"{item.symbol}:{item.signal_date}:data_cutoff_after_signal")
        if return_start and signal_ts and return_start <= signal_ts:
            violations.append(f"{item.symbol}:{item.signal_date}:return_start_not_after_signal")
        for field in fields:
            value = getattr(item, field, None)
            if value not in (None, "", {}, []):
                counts[field] += 1
        audited += 1
    return {
        "audited_count": audited,
        "field_presence_counts": counts,
        "violation_count": len(violations),
        "violations_sample": violations[:20],
        "policy": "data_cutoff_time <= signal_generated_at < return_start_time",
    }


def _market_adaptive_density(*, variants: dict[str, dict[str, Any]], evaluation_trade_days: int) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, variant in variants.items():
        market_rows = variant.get("by_market_state", [])
        grouped = {
            "good": _market_group_summary(market_rows, GOOD_MARKET_STATES, evaluation_trade_days),
            "weak": _market_group_summary(market_rows, WEAK_MARKET_STATES, evaluation_trade_days),
            "retreat": _market_group_summary(market_rows, RETREAT_MARKET_STATES, evaluation_trade_days),
            "unknown_or_other": _market_group_summary(
                market_rows,
                set(row.get("key", "") for row in market_rows)
                - GOOD_MARKET_STATES
                - WEAK_MARKET_STATES
                - RETREAT_MARKET_STATES,
                evaluation_trade_days,
            ),
        }
        good_density = grouped["good"]["signal_density_per_100_trade_days"]
        weak_density = grouped["weak"]["signal_density_per_100_trade_days"]
        retreat_density = grouped["retreat"]["signal_density_per_100_trade_days"]
        grouped["adaptive_density_ratio_good_vs_weak_retreat"] = round(good_density / max(weak_density + retreat_density, 0.01), 4)
        result[key] = grouped
    return result


def _market_group_summary(rows: list[dict[str, Any]], states: set[str], evaluation_trade_days: int) -> dict[str, Any]:
    selected = [row for row in rows if str(row.get("key") or "") in states]
    sample_count = sum(int(row.get("sample_count") or 0) for row in selected)
    filled_count = sum(int(row.get("filled_count") or 0) for row in selected)
    signal_days = sum(int(row.get("signal_days") or 0) for row in selected)
    return {
        "states": sorted(states),
        "sample_count": sample_count,
        "filled_count": filled_count,
        "signal_days": signal_days,
        "signal_density_per_100_trade_days": round(signal_days / max(evaluation_trade_days, 1) * 100.0, 4),
        "avg_trade_return_pct_avg": round(sum(float(row.get("avg_trade_return_pct") or 0.0) for row in selected) / max(len(selected), 1), 4),
        "profit_factor_avg": round(sum(float(row.get("profit_factor") or 0.0) for row in selected) / max(len(selected), 1), 4),
    }


def _no_signal_intervals(outcomes: list[Any], *, evaluation_dates: list[str]) -> dict[str, Any]:
    signal_dates = {str(item.signal_date) for item in outcomes if str(item.signal_date or "")}
    intervals: list[dict[str, Any]] = []
    current_start = ""
    current_length = 0
    previous = ""
    for trade_date in evaluation_dates:
        if trade_date in signal_dates:
            if current_length:
                intervals.append({"start": current_start, "end": previous, "trade_days": current_length})
            current_start = ""
            current_length = 0
        else:
            if current_length == 0:
                current_start = trade_date
            current_length += 1
        previous = trade_date
    if current_length:
        intervals.append({"start": current_start, "end": previous, "trade_days": current_length})
    intervals.sort(key=lambda item: (-int(item["trade_days"]), item["start"]))
    return {
        "longest_no_signal_trade_days": intervals[0]["trade_days"] if intervals else 0,
        "top_intervals": intervals[:10],
        "note": "该表按交易日计算无信号空窗；是否合理需结合行情状态分层解读。",
    }


def _precision_gate(variants: dict[str, dict[str, Any]], *, evaluation_dates: list[str]) -> dict[str, Any]:
    weighted = variants["front_row_weighted_max5"]
    stress = weighted.get("cost_stress", {}).get("extra_cost_30bps", {})
    max5 = stress.get("max5", {})
    max10 = stress.get("max10", {})
    return {
        "policy": "precision_first_market_adaptive_density",
        "signal_day_retention_is_blocker": False,
        "deprecated_signal_day_retention_threshold_pct": 75.0,
        "cost_adjusted_gate": {
            "extra_cost_bps": 30.0,
            "max5_pf": max5.get("profit_factor", 0.0),
            "max10_pf": max10.get("profit_factor", 0.0),
            "max5_avg_trade_return_pct": max5.get("avg_trade_return_pct", 0.0),
            "max10_avg_trade_return_pct": max10.get("avg_trade_return_pct", 0.0),
            "passed": _cost_gate_passed(weighted),
        },
        "tradability_gate": {
            **weighted.get("tradability_proxy", {}),
            "passed": _tradability_gate_passed(weighted),
        },
        "concentration_gate": {
            **weighted.get("portfolio_max5", {}).get("concentration", {}),
            "passed": _concentration_gate_passed(weighted),
        },
        "oos_gate": {
            **_oos_window_summary(weighted, evaluation_dates=evaluation_dates, quarters={"2026Q2"}),
            "minimum_required_trade_days": 60,
            "passed": _oos_window_summary(weighted, evaluation_dates=evaluation_dates, quarters={"2026Q2"})["oos_window_trade_days"] >= 60,
        },
    }


def _longest_no_signal_days(outcomes: list[Any]) -> int:
    signal_dates = sorted({str(item.signal_date) for item in outcomes if str(item.signal_date or "")})
    if len(signal_dates) < 2:
        return 0
    parsed = [date.fromisoformat(item) for item in signal_dates]
    return max((parsed[index] - parsed[index - 1]).days - 1 for index in range(1, len(parsed)))


def _evaluation_dates_local(
    *,
    trade_dates: list[str],
    start: str,
    latest_completed: str,
    forward_days: int,
    end: str,
) -> list[str]:
    cutoff_index = max(0, len(trade_dates) - max(forward_days, 0))
    completed = trade_dates[:cutoff_index] if cutoff_index else trade_dates
    upper = min(latest_completed, end or latest_completed)
    return [item for item in completed if item >= start and item <= upper]


def _data_source_summary(db) -> dict[str, Any]:
    daily_count, min_date, max_date = db.execute(select(func.count(DailyBarSnapshot.id), func.min(DailyBarSnapshot.trade_date), func.max(DailyBarSnapshot.trade_date))).one()
    symbol_count = db.execute(select(func.count(func.distinct(DailyBarSnapshot.symbol)))).scalar_one() or 0
    return {
        "database_url": _safe_database_url(),
        "daily_bar_count": int(daily_count or 0),
        "daily_min_trade_date": str(min_date or ""),
        "daily_max_trade_date": str(max_date or ""),
        "daily_symbol_count": int(symbol_count or 0),
    }


def _safe_database_url() -> str:
    raw = os.getenv("DATABASE_URL", "")
    if not raw:
        return ""
    if "@" not in raw:
        return raw
    prefix, suffix = raw.split("@", 1)
    scheme = prefix.split(":", 1)[0]
    return f"{scheme}:***@{suffix}"


def _merge_counts(*items: dict[str, int]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for item in items:
        counter.update({str(key): int(value or 0) for key, value in (item or {}).items()})
    return dict(sorted(counter.items(), key=lambda pair: (-pair[1], pair[0])))


def _quarter(value: str) -> str:
    if not value:
        return "unknown"
    parsed = date.fromisoformat(str(value)[:10])
    return f"{parsed.year}Q{((parsed.month - 1) // 3) + 1}"


def _pct(value: int | float, total: int | float) -> float:
    return round(float(value or 0.0) / max(float(total or 0.0), 1.0) * 100.0, 2)


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 前排加权生产评分 Shadow/Paper 组合回测",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 评估窗口：{report['scope']['actual_evaluation_start']} 至 {report['scope']['actual_evaluation_end']}，{report['scope']['evaluation_trade_days']} 个交易日。",
        f"- 配置版本：`{report['config']['production_scoring_config_version']}`",
        "- 结论：{status}；建议小流量生产观察：{recommend}。".format(
            status=report["decision"]["status"],
            recommend="是" if report["decision"]["recommend_small_traffic_observation"] else "否",
        ),
        f"- 决策口径：`{report['decision'].get('decision_policy', 'precision_first_market_adaptive_density')}`。",
        "",
        "## 核心约束",
        "",
        "- `front_row_only` 只作为对照，不作为生产硬过滤方案。",
        "- `production_score` 只允许 `buy_now` / `soft_buy_now` 生成；`near_entry` 只能进入观察池。",
        "- 旧“总收益率”按“每日信号等权复利收益”展示，且只作为信号质量参考；真实组合收益单独展示。",
        "- 本次只接入 Shadow 与 Paper 回测，未替换生产排序，未部署上线。",
        "- 信号少不再单独扣分；验收改为成本后精准度、行情自适应密度、OOS 长度、可成交性和集中度。",
        "",
        "## 变体对比：样本与信号质量口径",
        "",
        "> 本表的收益、最大回撤、PF、平均单笔均为“每日信号等权/信号质量”口径，不能当作真实账户收益。",
        "",
        "| 候选池变体 | 样本 | 成交 | 信号日 | 最长无票 | 每日信号等权复利收益 | 信号质量最大回撤 | 信号质量PF | 信号质量平均单笔 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key in report.get("display_variant_order", DISPLAY_VARIANTS):
        item = report["display_variants"][key]
        signal = item["signal_quality"]
        lines.append(
            "| {key} | {sample_count} | {filled_count} | {signal_days} | {longest_no_signal_days} | {daily:.2f}% | {mdd:.2f}% | {pf:.2f} | {avg:.3f}% |".format(
                key=key,
                sample_count=item["sample_count"],
                filled_count=item["filled_count"],
                signal_days=item["signal_days"],
                longest_no_signal_days=item["longest_no_signal_days"],
                daily=signal["daily_signal_equal_weight_compound_return_pct"],
                mdd=signal["max_drawdown_pct"],
                pf=signal["profit_factor"],
                avg=signal["avg_trade_return_pct"],
            )
        )
    lines.extend([
        "",
        "## 真实组合口径",
        "",
        "> 本表才是更接近账户的组合收益口径，包含资金占用、同票去重、策略/板块限制、弱市仓位限制和退潮不开仓。",
        "",
        "| 候选池变体 | max5收益 | max5回撤 | max5 PF | max5平均单笔 | max5资金利用 | max5交易数 | max10收益 | max10回撤 | max10 PF | max10平均单笔 | max10资金利用 | max10交易数 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for key in report.get("display_variant_order", DISPLAY_VARIANTS):
        portfolio = report["display_variants"][key]["real_portfolio"]
        max5 = portfolio["max5"]
        max10 = portfolio["max10"]
        lines.append(
            "| {key} | {max5_return:.2f}% | {max5_mdd:.2f}% | {max5_pf:.2f} | {max5_avg:.3f}% | {max5_util:.2f}% | {max5_trades} | {max10_return:.2f}% | {max10_mdd:.2f}% | {max10_pf:.2f} | {max10_avg:.3f}% | {max10_util:.2f}% | {max10_trades} |".format(
                key=key,
                max5_return=max5["return_pct"],
                max5_mdd=max5["max_drawdown_pct"],
                max5_pf=max5["profit_factor"],
                max5_avg=max5["avg_trade_return_pct"],
                max5_util=max5["avg_capital_utilization_pct"],
                max5_trades=max5["trade_count"],
                max10_return=max10["return_pct"],
                max10_mdd=max10["max_drawdown_pct"],
                max10_pf=max10["profit_factor"],
                max10_avg=max10["avg_trade_return_pct"],
                max10_util=max10["avg_capital_utilization_pct"],
                max10_trades=max10["trade_count"],
            )
        )
    lines.extend([
        "",
        "## 成本压力测试",
        "",
        f"> 基础执行模型已扣 `{ROUND_TRIP_COST_BPS:.0f}bps` 往返成本；下表继续额外扣除滑点/冲击成本，用于压力测试。",
        "",
        "| 额外成本 | max5收益 | max5 PF | max5平均单笔 | max10收益 | max10 PF | max10平均单笔 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    stress = report["variants"]["front_row_weighted_max5"]["cost_stress"]
    for key in sorted(stress, key=lambda item: int(item.split("_")[-1].replace("bps", ""))):
        item = stress[key]
        max5 = item["max5"]
        max10 = item["max10"]
        lines.append(
            "| +{extra:.0f}bps | {max5_return:.2f}% | {max5_pf:.2f} | {max5_avg:.3f}% | {max10_return:.2f}% | {max10_pf:.2f} | {max10_avg:.3f}% |".format(
                extra=item["extra_cost_bps"],
                max5_return=max5["return_pct"],
                max5_pf=max5["profit_factor"],
                max5_avg=max5["avg_trade_return_pct"],
                max10_return=max10["return_pct"],
                max10_pf=max10["profit_factor"],
                max10_avg=max10["avg_trade_return_pct"],
            )
        )
    lines.extend([
        "",
        "## 相对 Baseline",
        "",
        "| 变体 | 样本留存 | 成交留存 | 信号日留存 | 每日信号等权复利变化 | max5真实组合变化 | max10真实组合变化 | 信号质量最大回撤改善 | 信号质量PF变化 | 最长无票变化 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for key, item in report["comparisons"].items():
        if key == "front_row_weighted_max10":
            continue
        display_key = "front_row_weighted" if key == "front_row_weighted_max5" else key
        lines.append(
            "| {key} | {sample_retention_rate_pct:.2f}% | {filled_retention_rate_pct:.2f}% | {signal_day_retention_rate_pct:.2f}% | {daily_signal_equal_weight_compound_return_pct_delta:+.2f}% | {real_portfolio_max5_return_pct_delta:+.2f}% | {real_portfolio_max10_return_pct_delta:+.2f}% | {max_drawdown_reduction_pct:+.2f}% | {profit_factor_delta:+.3f} | {longest_no_signal_days_delta:+d} |".format(
                key=display_key,
                **item,
            )
        )
    lines.extend([
        "",
        "## 信号状态拆分",
        "",
    ])
    lines.extend(_breakdown_table(report["signal_state_breakdown"].get("front_row_weighted_max5", [])))
    lines.extend([
        "",
        "## 前排分层拆分",
        "",
    ])
    lines.extend(_breakdown_table(report["front_row_tier_breakdown"].get("front_row_weighted_max5", [])))
    lines.extend([
        "",
        "## 行情自适应密度",
        "",
        "| 变体 | 强势/修复信号日 | 弱市信号日 | 退潮信号日 | 强弱退密度比 | 强势平均单笔 | 弱市平均单笔 | 退潮平均单笔 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for key in ("baseline", "front_row_only", "front_row_weighted"):
        source_key = "front_row_weighted_max5" if key == "front_row_weighted" else key
        item = report["market_adaptive_density"][source_key]
        lines.append(
            "| {key} | {good_days} | {weak_days} | {retreat_days} | {ratio:.2f} | {good_avg:.3f}% | {weak_avg:.3f}% | {retreat_avg:.3f}% |".format(
                key=key,
                good_days=item["good"]["signal_days"],
                weak_days=item["weak"]["signal_days"],
                retreat_days=item["retreat"]["signal_days"],
                ratio=item["adaptive_density_ratio_good_vs_weak_retreat"],
                good_avg=item["good"]["avg_trade_return_pct_avg"],
                weak_avg=item["weak"]["avg_trade_return_pct_avg"],
                retreat_avg=item["retreat"]["avg_trade_return_pct_avg"],
            )
        )
    lines.extend([
        "",
        "## 可成交性代理与集中度",
        "",
        "| 变体 | T+1锁涨停率 | T+1开盘高于入场区代理 | max5前10笔正收益贡献 | max5单票最大正收益贡献 | max5平均单笔CI95 |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for key in ("baseline", "front_row_only", "front_row_weighted"):
        source_key = "front_row_weighted_max5" if key == "front_row_weighted" else key
        variant = report["variants"][source_key]
        proxy = variant["tradability_proxy"]
        concentration = variant["portfolio_max5"].get("concentration", {})
        ci = concentration.get("bootstrap_avg_trade_return_ci95_pct", {})
        ci_text = "{low:.3f}%~{high:.3f}%".format(low=ci.get("low", 0.0), high=ci.get("high", 0.0))
        lines.append(
            "| {key} | {locked:.2f}% | {gap:.2f}% | {top10:.2f}% | {symbol:.2f}% | {ci} |".format(
                key=key,
                locked=proxy.get("t1_locked_limit_up_rate_pct", 0.0),
                gap=proxy.get("t1_open_gap_above_entry_zone_rate_pct", 0.0),
                top10=concentration.get("top_10_positive_trade_contribution_pct", 0.0),
                symbol=concentration.get("max_symbol_positive_contribution_pct", 0.0),
                ci=ci_text,
            )
        )
    lines.extend([
        "",
        "## 组合跳过原因",
        "",
        "| 变体 | max5跳过 | max10跳过 | 同票重复 | 同策略日超限 | 同板块超限 | 退潮不开仓 | 弱市场仓位上限 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for display_key in report.get("display_variant_order", DISPLAY_VARIANTS):
        key = "front_row_weighted_max5" if display_key == "front_row_weighted" else display_key
        item = report["variants"][key]
        max5 = item["portfolio_max5"]
        max10 = item["portfolio_max10"]
        lines.append(
            "| {key} | {max5_skip} | {max10_skip} | {duplicate} | {strategy} | {sector} | {retreat} | {weak} |".format(
                key=display_key,
                max5_skip=max5["skipped_count"],
                max10_skip=max10["skipped_count"],
                duplicate=max5["skipped_by_duplicate_symbol"] + max10["skipped_by_duplicate_symbol"],
                strategy=max5["skipped_by_strategy_daily_limit"] + max10["skipped_by_strategy_daily_limit"],
                sector=max5["skipped_by_sector_limit"] + max10["skipped_by_sector_limit"],
                retreat=max5["skipped_by_retreat_market"] + max10["skipped_by_retreat_market"],
                weak=max5["skipped_by_weak_market_position_cap"] + max10["skipped_by_weak_market_position_cap"],
            )
        )
    lines.extend([
        "",
        "## 防未来函数与防过拟合",
        "",
        f"- 防未来函数审计：{report['anti_future_function_audit']['future_leak_check']}。",
        f"- 时间切分：train={report['anti_overfit_policy']['train']}；validation={report['anti_overfit_policy']['validation']}；oos={report['anti_overfit_policy']['oos']}。",
        f"- OOS 状态：{report['time_series_splits']['oos']['status']}；最低要求 {report['time_series_splits']['oos']['minimum_trade_days_required']} 个交易日。",
        "- 禁止随机切分；本次不根据样本外结果反向调权重。",
        f"- 字段级 asof 审计策略：{report['variants']['front_row_weighted_max5']['field_asof_audit']['policy']}。",
        "",
        "## 决策",
        "",
    ])
    blockers = report["decision"]["blockers"]
    if blockers:
        lines.extend(f"- 阻断：{item}" for item in blockers)
    else:
        lines.append("- Shadow/Paper 指标满足最低观察条件，可考虑后续小流量观察。")
    warnings = report["decision"].get("warnings", [])
    if warnings:
        lines.extend(f"- 警告：{item}" for item in warnings)
    deprecated = report["decision"].get("deprecated_blockers", [])
    if deprecated:
        lines.extend(f"- 已废弃阻断项：{item}" for item in deprecated)
    lines.extend(f"- {item}" for item in report["decision"]["notes"])
    return "\n".join(lines) + "\n"


def _breakdown_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| 分组 | 样本 | 成交 | 每日信号等权复利收益 | 真实组合max5 | 最大回撤 | PF | 平均单笔 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    if not rows:
        lines.append("| 无 | 0 | 0 | 0.00% | 0.00% | 0.00% | 0.00 | 0.000% |")
        return lines
    for item in rows:
        lines.append(
            "| {key} | {sample_count} | {filled_count} | {daily_signal_equal_weight_compound_return_pct:.2f}% | {real_portfolio_max5_return_pct:.2f}% | {max_drawdown_pct:.2f}% | {profit_factor:.2f} | {avg_trade_return_pct:.3f}% |".format(**item)
        )
    return lines


if __name__ == "__main__":
    raise SystemExit(main())
