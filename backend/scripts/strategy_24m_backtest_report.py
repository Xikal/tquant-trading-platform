from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "backend"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.core.database import SessionLocal, init_db
from app.models.entities import DailyBarSnapshot, MinuteBarSnapshot
from app.services.etf.universe import list_etf_profiles
from app.services.low_buy.execution_simulation import ExecutionSimulationOverride
from app.services.low_buy.front_row_filter import FrontRowFilterConfig
from app.services.low_buy_screener import PLAYBOOKS, LowBuyScreenerService

try:
    from .low_buy_market_backtest import _count_signal_state, _load_a_share_universe_count
    from .low_buy_market_backtest_reporting import CONFIRMED_STATES, EVALUATED_STATES, StrategyBacktestStats, build_report, history_window_days
    from .low_buy_market_backtest_runner import run_fast_isolated_execution_matrix_backtest
    from .strategy_24m_front_row_filter import front_row_filter_ab_summary
    from .strategy_24m_report_markdown import render_markdown
    from .strategy_24m_report_metrics import (
        abnormal_strategies,
        group_breakdown,
        parameter_suggestions,
        quarter,
        rank_strategies,
        signal_state_breakdown,
        strategy_detail,
        strategy_family_summary,
    )
    from .strategy_24m_report_sections import (
        data_and_test_gaps,
        etf_t0_section,
        production_conclusion,
        sector_etf_t0_section,
        smart_t_section,
    )
    from .strategy_24m_static_attribution import attach_static_sector_breakdowns, load_static_sector_map, static_sector_breakdown
except ImportError:
    from low_buy_market_backtest import _count_signal_state, _load_a_share_universe_count
    from low_buy_market_backtest_reporting import CONFIRMED_STATES, EVALUATED_STATES, StrategyBacktestStats, build_report, history_window_days
    from low_buy_market_backtest_runner import run_fast_isolated_execution_matrix_backtest
    from strategy_24m_front_row_filter import front_row_filter_ab_summary
    from strategy_24m_report_markdown import render_markdown
    from strategy_24m_report_metrics import (
        abnormal_strategies,
        group_breakdown,
        parameter_suggestions,
        quarter,
        rank_strategies,
        signal_state_breakdown,
        strategy_detail,
        strategy_family_summary,
    )
    from strategy_24m_report_sections import (
        data_and_test_gaps,
        etf_t0_section,
        production_conclusion,
        sector_etf_t0_section,
        smart_t_section,
    )
    from strategy_24m_static_attribution import attach_static_sector_breakdowns, load_static_sector_map, static_sector_breakdown


DEFAULT_START = "2024-05-28"
DEFAULT_JSON_OUTPUT = ROOT_DIR / "docs" / "reports" / "strategy-24m-backtest-2026-05-28.json"
DEFAULT_MD_OUTPUT = ROOT_DIR / "docs" / "reports" / "strategy-24m-backtest-2026-05-28.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="全策略 24 个月上线前回测报告")
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default="")
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MD_OUTPUT))
    parser.add_argument("--existing-report", default="")
    parser.add_argument("--refresh-sections-only", action="store_true")
    parser.add_argument("--scan-limit", type=int, default=480)
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--forward-days", type=int, default=5)
    parser.add_argument("--target-profit-pct", type=float, default=3.0)
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
        if args.refresh_sections_only:
            enriched = _refresh_existing_report(db, args)
        else:
            enriched = _run_backtest_report(db, args)

    output_json.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(render_markdown(enriched), encoding="utf-8")
    print(json.dumps({"json": str(output_json), "markdown": str(output_md), "summary": enriched["summary"]}, ensure_ascii=False, indent=2))
    return 0


def _run_backtest_report(db, args: argparse.Namespace) -> dict[str, Any]:
    service = LowBuyScreenerService()
    source = _data_source_summary(db)
    trade_dates = _trade_dates(db)
    latest_available = _latest_available_trade_date(source)
    requested_end = args.end or latest_available
    latest_completed = min(service._resolve_latest_completed_trade_date(trade_dates), requested_end)
    evaluation_dates = _evaluation_dates(
        trade_dates=trade_dates,
        start=args.start,
        latest_completed=latest_completed,
        forward_days=args.forward_days,
        end=requested_end,
    )
    strategy_keys = list(PLAYBOOKS.keys())
    stats = _initial_stats(strategy_keys)
    front_row_stats = _initial_stats(strategy_keys)
    execution_override = ExecutionSimulationOverride(enforce_t1_exit_rules=True)
    front_row_config = FrontRowFilterConfig(enabled=True)
    run_fast_isolated_execution_matrix_backtest(
        db=db,
        service=service,
        stats_by_variant={
            "baseline": stats,
            "front_row_only": front_row_stats,
        },
        trade_dates=trade_dates,
        evaluation_dates=evaluation_dates,
        latest_completed=latest_completed,
        strategy_keys=strategy_keys,
        evaluated_states=set(EVALUATED_STATES),
        execution_overrides={
            "baseline": execution_override,
            "front_row_only": execution_override,
        },
        market_guard=None,
        scan_limit=args.scan_limit,
        limit=args.limit,
        forward_days=args.forward_days,
        history_window_days_value=history_window_days(args.months, args.forward_days),
        count_signal_state=_count_signal_state,
        front_row_filters={
            "front_row_only": front_row_config,
        },
    )
    base_report = build_report(
        universe_count=_load_a_share_universe_count(db, service),
        latest_completed=latest_completed,
        evaluation_dates=evaluation_dates,
        target_profit_pct=args.target_profit_pct,
        scan_limit=args.scan_limit,
        months=args.months,
        materialization_mode="isolated/fast,matrix=baseline+front_row_only",
        stats=list(stats.values()),
        requested_start=args.start,
        requested_end=requested_end,
        selected_states=set(EVALUATED_STATES),
        execution_model_label="candidate_exit_plan,enforce_a_share_t1_exit_rules,cost=16bps",
        market_guard_label="none",
        prefilter_override_label="none",
    )
    front_row_filter = front_row_filter_ab_summary(
        baseline_stats=stats,
        front_row_stats=front_row_stats,
        config=front_row_config,
    )
    return _build_enriched_report(
        db=db,
        args=args,
        source=source,
        latest_completed=latest_completed,
        evaluation_dates=evaluation_dates,
        stats=stats,
        base_report=base_report,
        front_row_filter=front_row_filter,
    )


def _initial_stats(strategy_keys: list[str]) -> dict[str, StrategyBacktestStats]:
    return {
        strategy: StrategyBacktestStats(
            strategy_key=strategy,
            strategy_title=PLAYBOOKS[strategy]["title"],
            strategy_family=_strategy_family(strategy),
            strategy_family_text=_strategy_family_label(strategy),
        )
        for strategy in strategy_keys
    }


def _build_enriched_report(
    *,
    db,
    args: argparse.Namespace,
    source: dict[str, Any],
    latest_completed: str,
    evaluation_dates: list[str],
    stats: dict[str, StrategyBacktestStats],
    base_report: dict[str, Any],
    front_row_filter: dict[str, Any] | None = None,
) -> dict[str, Any]:
    coverage = _coverage(args.start, source.get("daily_min_trade_date", ""), source.get("daily_max_trade_date", ""))
    all_outcomes = [outcome for stat in stats.values() for outcome in stat.outcomes]
    strategies = [strategy_detail(key, stats[key]) for key in stats]
    sector_by_symbol = load_static_sector_map(db)
    strategies = attach_static_sector_breakdowns(strategies, stats, sector_by_symbol)
    return _assemble_report(
        db=db,
        args=args,
        source=source,
        latest_completed=latest_completed,
        evaluation_dates=evaluation_dates,
        coverage=coverage,
        strategies=strategies,
        all_outcomes=all_outcomes,
        sector_breakdown=static_sector_breakdown(all_outcomes, sector_by_symbol, limit=30),
        base_report=base_report,
        front_row_filter=front_row_filter,
    )


def _refresh_existing_report(db, args: argparse.Namespace) -> dict[str, Any]:
    source = _data_source_summary(db)
    report_path = Path(args.existing_report or args.json_output)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    scope = report.get("scope", {})
    window = scope.get("actual_evaluation_window", {})
    evaluation_dates = _trade_dates_in_window(db, start=window.get("start", ""), end=window.get("end", ""))
    latest_completed = window.get("end") or report.get("summary", {}).get("actual_evaluation_end") or source.get("daily_max_trade_date", "")
    coverage = _coverage(args.start, source.get("daily_min_trade_date", ""), source.get("daily_max_trade_date", ""))
    strategies = _refresh_strategy_family_metadata(list(report.get("all_strategies") or []))
    all_outcomes: list[Any] = []
    refreshed = _assemble_report(
        db=db,
        args=args,
        source=source,
        latest_completed=latest_completed,
        evaluation_dates=evaluation_dates,
        coverage=coverage,
        strategies=strategies,
        all_outcomes=all_outcomes,
        sector_breakdown=report.get("performance_by_sector", {}),
        base_report={"summary": report.get("raw_low_buy_report_summary") or report.get("summary", {}), "methodology": report.get("methodology", {})},
        front_row_filter=report.get("front_row_filter"),
    )
    for key in ("performance_by_family", "performance_by_quarter", "performance_by_market_state", "performance_by_signal_state", "performance_by_sector"):
        refreshed[key] = report.get(key, [])
    report.update(refreshed)
    report["generated_at"] = datetime.now().isoformat(timespec="seconds")
    return report


def _assemble_report(
    *,
    db,
    args: argparse.Namespace,
    source: dict[str, Any],
    latest_completed: str,
    evaluation_dates: list[str],
    coverage: dict[str, Any],
    strategies: list[dict[str, Any]],
    all_outcomes: list[Any],
    sector_breakdown: dict[str, Any] | list[dict[str, Any]],
    base_report: dict[str, Any],
    front_row_filter: dict[str, Any] | None = None,
) -> dict[str, Any]:
    end = source.get("daily_max_trade_date", "")
    etf_t0 = etf_t0_section(db, start=args.start, end=end)
    sector_etf_t0 = sector_etf_t0_section(db, source=source)
    smart_t = smart_t_section(db, args=args, source=source, latest_completed=latest_completed)
    summary = {
        **base_report["summary"],
        "requested_start": args.start,
        "requested_end": end,
        "actual_data_start": source.get("daily_min_trade_date", ""),
        "actual_data_end": end,
        "actual_evaluation_start": evaluation_dates[0] if evaluation_dates else "",
        "actual_evaluation_end": evaluation_dates[-1] if evaluation_dates else "",
        "coverage_pct": coverage["coverage_pct"],
        "coverage_status": coverage["status"],
        "coverage_warning": coverage["warning"],
        "execution_constraints": _execution_constraints(),
    }
    parameter_changes = parameter_suggestions(strategies)
    family_rows = group_breakdown(
        all_outcomes,
        lambda item: _strategy_family(item.strategy_key),
        title_lookup=_strategy_family_label,
        states=set(CONFIRMED_STATES),
    )
    return {
        "title": "全策略最近 24 个月回测报告",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "scope": {
            "current_date": "2026-05-29",
            "requested_window": {"start": args.start, "end": end},
            "actual_evaluation_window": {"start": evaluation_dates[0] if evaluation_dates else "", "end": evaluation_dates[-1] if evaluation_dates else "", "trade_days": len(evaluation_dates)},
            "strategy_count": len(strategies),
            "strategy_keys": [item.get("strategy_key", "") for item in strategies],
        },
        "data_source": source,
        "inventory": _inventory_section(),
        "coverage": coverage,
        "methodology": base_report.get("methodology", {}),
        "summary": summary,
        "front_row_filter_summary": _front_row_filter_summary(front_row_filter),
        "front_row_filter": front_row_filter or _empty_front_row_filter_payload(),
        "all_strategies": strategies,
        "strategy_ranking": rank_strategies(strategies),
        "strategy_family_summary": strategy_family_summary(
            strategies,
            family_rows,
            parameter_changes,
        ),
        "performance_by_family": family_rows,
        "performance_by_quarter": group_breakdown(all_outcomes, lambda item: quarter(item.signal_date), states=set(CONFIRMED_STATES)),
        "performance_by_market_state": group_breakdown(all_outcomes, lambda item: item.market_state or "unknown", states=set(CONFIRMED_STATES)),
        "performance_by_signal_state": signal_state_breakdown(all_outcomes),
        "performance_by_sector": sector_breakdown,
        "etf_t0": etf_t0,
        "sector_etf_t0": sector_etf_t0,
        "smart_t": smart_t,
        "abnormal_strategies": abnormal_strategies(strategies),
        "parameter_adjustment_suggestions": parameter_changes,
        "data_and_test_gaps": data_and_test_gaps(coverage, etf_t0, sector_etf_t0, smart_t, strategies),
        "production_observation_conclusion": production_conclusion(strategies, etf_t0, sector_etf_t0, smart_t, coverage),
        "raw_low_buy_report_summary": base_report["summary"],
    }


def _data_source_summary(db) -> dict[str, Any]:
    daily_count, min_date, max_date = db.execute(select(func.count(DailyBarSnapshot.id), func.min(DailyBarSnapshot.trade_date), func.max(DailyBarSnapshot.trade_date))).one()
    symbol_count = db.execute(select(func.count(func.distinct(DailyBarSnapshot.symbol)))).scalar_one() or 0
    stock_count = db.execute(select(func.count(func.distinct(DailyBarSnapshot.symbol))).where(DailyBarSnapshot.instrument_type == "stock")).scalar_one() or 0
    minute_count, minute_min, minute_max = db.execute(select(func.count(MinuteBarSnapshot.id), func.min(MinuteBarSnapshot.trade_date), func.max(MinuteBarSnapshot.trade_date))).one()
    return {
        "database_url": _safe_database_url(),
        "daily_bar_count": int(daily_count or 0),
        "daily_min_trade_date": str(min_date or ""),
        "daily_max_trade_date": str(max_date or ""),
        "daily_symbol_count": int(symbol_count or 0),
        "daily_stock_symbol_count": int(stock_count or 0),
        "minute_bar_count": int(minute_count or 0),
        "minute_min_trade_date": str(minute_min or ""),
        "minute_max_trade_date": str(minute_max or ""),
    }


def _refresh_strategy_family_metadata(strategies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refreshed: list[dict[str, Any]] = []
    for item in strategies:
        strategy_key = str(item.get("strategy_key") or "")
        updated = dict(item)
        updated["strategy_family"] = _strategy_family(strategy_key)
        updated["strategy_family_text"] = _strategy_family_label(strategy_key)
        refreshed.append(updated)
    return refreshed


def _coverage(start: str, actual_start: str, actual_end: str) -> dict[str, Any]:
    if not actual_start or not actual_end:
        return {"status": "empty", "coverage_pct": 0.0, "missing_reason": "本地 daily_bar_snapshots 为空。", "warning": "无可回测日线数据，不能验收。"}
    requested_start = date.fromisoformat(start)
    requested_end = date.fromisoformat(actual_end)
    actual_start_date = date.fromisoformat(actual_start)
    requested_days = max((requested_end - requested_start).days + 1, 1)
    covered_start = max(requested_start, actual_start_date)
    covered_days = max((date.fromisoformat(actual_end) - covered_start).days + 1, 0)
    pct = round(min(covered_days / requested_days * 100.0, 100.0), 2)
    status = "complete" if pct >= 95.0 else "partial"
    missing_reason = "" if status == "complete" else f"本地日线最早为 {actual_start}，缺少 {start} 至 {(actual_start_date - timedelta(days=1)).isoformat()}。"
    warning = "" if status == "complete" else "本地数据不足 24 个月，不能作为完整 24 个月上线验收。"
    return {"status": status, "coverage_pct": pct, "requested_calendar_days": requested_days, "covered_calendar_days": covered_days, "missing_reason": missing_reason, "warning": warning}


def _inventory_section() -> dict[str, Any]:
    return {
        "strategy_source": "app.services.low_buy_screener.PLAYBOOKS",
        "strategy_count": len(PLAYBOOKS),
        "strategies": [{"strategy_key": key, "strategy_title": value.get("title", key)} for key, value in PLAYBOOKS.items()],
        "implemented_strategy_groups": [
            {"key": "low_buy_playbooks", "title": "低吸/选股策略", "count": len(PLAYBOOKS), "source": "app.services.low_buy.shared.PLAYBOOKS"},
            {"key": "etf_t0", "title": "ETF T0 分钟级做T", "count": len([profile for profile in list_etf_profiles() if profile.same_day_sell_allowed]), "source": "app.services.etf.t0_backtest"},
            {"key": "sector_etf_t0", "title": "行业 ETF 替代做T", "count": 1, "source": "app.services.sector_etf_t0"},
            {"key": "smart_t", "title": "个股底仓 SmartT 做T", "count": 1, "source": "legacy research module (paper runtime disabled)"},
        ],
        "backtest_scripts": [
            "backend/scripts/low_buy_market_backtest.py",
            "backend/scripts/low_buy_market_backtest_runner.py",
            "backend/scripts/low_buy_market_backtest_outcomes.py",
            "backend/scripts/low_buy_market_backtest_reporting.py",
            "backend/scripts/low_buy_execution_matrix.py",
            "backend/scripts/strategy_24m_backtest_report.py",
            "backend/app/services/etf/t0_backtest.py",
            "backend/app/services/sector_etf_t0.py",
        ],
        "backtest_api": ["/api/backtests", "/api/backtests/etf-t0-minute", "/api/backtests/etf-t0-research", "/api/backtests/etf-t0-oos/*"],
        "data_sources": ["daily_bar_snapshots", "minute_bar_snapshots", "low_buy_result_snapshots", "market_model_observations", "ETF universe runtime/static profiles"],
        "existing_report_locations": ["backend/data/reports/", "research/reports/", "docs/reports/"],
    }


def _front_row_filter_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {
            "status": "not_run",
            "decision": "not_run",
            "sample_retention_rate_pct": 0.0,
            "filled_retention_rate_pct": 0.0,
            "signal_day_retention_rate_pct": 0.0,
            "avg_trade_return_pct_delta": 0.0,
            "profit_factor_delta": 0.0,
            "total_return_pct_delta": 0.0,
            "daily_signal_equal_weight_compound_return_pct_delta": 0.0,
            "max_drawdown_reduction_pct": 0.0,
            "notes": ["本次未执行前排过滤 A/B 回测。"],
        }
    delta = payload.get("delta") or {}
    return {
        "status": payload.get("status", "research_only"),
        "decision": payload.get("decision", "research_only"),
        "sample_retention_rate_pct": delta.get("sample_retention_rate_pct", 0.0),
        "filled_retention_rate_pct": delta.get("filled_retention_rate_pct", 0.0),
        "signal_day_retention_rate_pct": delta.get("signal_day_retention_rate_pct", 0.0),
        "avg_trade_return_pct_delta": delta.get("avg_trade_return_pct_delta", 0.0),
        "profit_factor_delta": delta.get("profit_factor_delta", 0.0),
        "total_return_pct_delta": delta.get("total_return_pct_delta", 0.0),
        "daily_signal_equal_weight_compound_return_pct_delta": delta.get("daily_signal_equal_weight_compound_return_pct_delta", delta.get("total_return_pct_delta", 0.0)),
        "max_drawdown_reduction_pct": delta.get("max_drawdown_reduction_pct", 0.0),
        "notes": list(payload.get("notes") or []),
    }


def _empty_front_row_filter_payload() -> dict[str, Any]:
    return {
        "status": "not_run",
        "enabled_variant": "front_row_only",
        "production_parameter_change_allowed": False,
        "sorting_effect": "none",
        "metric_basis": "not_run",
        "config": {},
        "anti_future_function_policy": {
            "signal_uses_future_data": False,
            "baseline_and_variant_share_signal_time": True,
            "post_signal_return_starts_after_signal": True,
            "random_split_allowed": False,
            "production_gate": "not_run",
        },
        "baseline": {},
        "front_row_only": {},
        "delta": {},
        "by_strategy": [],
        "by_market_state": [],
        "by_quarter": [],
        "notes": ["本次未执行前排过滤 A/B 回测。"],
        "decision": "not_run",
    }


def _execution_constraints() -> list[str]:
    return [
        "低吸个股回测启用 A 股 T+1 退出约束：入场当日不触发卖出型止盈/止损，开盘低于止损视为不可安全持有的风险退出。",
        "低吸回测按 ROUND_TRIP_COST_BPS=16bps 扣除往返成本。",
        "ETF T0 回测必须用窗口内分钟线、ETF 专用费用模型、滑点和同日回转约束；短窗口分钟线不能视为 24 个月验收。",
        "行业 ETF 替代做T sector_etf_t0 单独检查影子观察；本地分钟线不足时不能完成 T0 主策略验收。",
        "前排票过滤仅作为研究/影子观察变体，默认不改变生产优先榜；所有对比使用相同信号日候选，避免后验选股。",
        "生产收益排行仅使用 buy_now / soft_buy_now；near_entry 单独展示为观察提前量，不进入生产排行。",
        "真实组合回测新增最大持仓 5/10 两档，持仓期间占用资金，同票持有中禁止重复买入。",
        "回测只读，不修改生产策略参数。",
    ]


def _safe_database_url() -> str:
    value = os.environ.get("DATABASE_URL", "")
    if "@" not in value:
        return value
    prefix, suffix = value.split("@", 1)
    scheme = prefix.split("://", 1)[0] if "://" in prefix else "database"
    return f"{scheme}://***@{suffix}"


def _trade_dates(db) -> list[str]:
    return [str(item) for item in db.execute(select(DailyBarSnapshot.trade_date).distinct().order_by(DailyBarSnapshot.trade_date.asc())).scalars().all()]


def _trade_dates_in_window(db, *, start: str, end: str) -> list[str]:
    if not start or not end:
        return []
    return [item for item in _trade_dates(db) if start <= item <= end]


def _latest_available_trade_date(source: dict[str, Any]) -> str:
    return str(source.get("daily_max_trade_date") or "")


def _evaluation_dates(*, trade_dates: list[str], start: str, latest_completed: str, forward_days: int, end: str) -> list[str]:
    completed = [item for item in trade_dates if start <= item <= latest_completed and item <= end]
    if len(completed) <= forward_days:
        return []
    last_evaluable = completed[-1 - forward_days]
    return [item for item in completed if item <= last_evaluable]


def _strategy_family(strategy_key: str) -> str:
    from app.services.low_buy.strategy_families import resolve_strategy_family

    return resolve_strategy_family(strategy_key)


def _strategy_family_label(strategy_key: str) -> str:
    from app.services.low_buy.strategy_families import resolve_strategy_family_label

    return resolve_strategy_family_label(strategy_key)


if __name__ == "__main__":
    raise SystemExit(main())
