#!/usr/bin/env python3
"""Build a conservative 24-month strategy optimization review report."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
for path in (Path(__file__).resolve().parent, ROOT / "backend", ROOT / "backend" / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from strategy_24m_execution_matrix_evidence import load_execution_matrix_evidence  # noqa: E402
from strategy_24m_acceleration import acceleration_summary  # noqa: E402
from strategy_24m_report_metrics import strategy_family_summary  # noqa: E402
from strategy_24m_model_reviews import model_reviews  # noqa: E402
from strategy_24m_optimization_markdown import render_markdown  # noqa: E402
from strategy_24m_parameter_plans import candidate_param_plan  # noqa: E402
from strategy_24m_signal_diagnostics import buy_signal_diagnosis  # noqa: E402
from strategy_24m_scope_coverage import scope_coverage  # noqa: E402
from strategy_24m_walk_forward_matrix import walk_forward_matrix  # noqa: E402
from strategy_24m_completion_flags import (  # noqa: E402
    blocking_data_gates,
    missing_required_metrics,
    sector_breakdown_or_missing,
    unfinished_items,
)

from app.services.low_buy.strategy_parameter_defaults_parts.low_buy import (  # noqa: E402
    LOW_BUY_STRATEGY_EXECUTION_DEFAULTS,
    LOW_BUY_STRATEGY_PREFILTER_DEFAULTS,
)
from app.services.low_buy.strategy_policy import (  # noqa: E402
    get_strategy_tier,
    strategy_layer,
    strong_buy_paused,
)


SOURCE_DATE = "2026-05-28"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_sources(root: Path, source_date: str) -> dict[str, Any]:
    report_dir = root / "docs" / "reports"
    related_dir = report_dir / f"main-force-related-strategy-backtest-{source_date}"
    return {
        "strategy_24m": _load_json(report_dir / f"strategy-24m-backtest-{source_date}.json"),
        "closed_loop": _load_json(
            report_dir / f"strategy-improvement-closed-loop-{source_date}.json"
        ),
        "main_force": _load_json(
            report_dir / f"main-force-model-production-readiness-{source_date}.json"
        ),
        "related_strategy": _load_json(
            related_dir
            / "low_buy_market_backtest_24m_all_states_default_exit_no_guard_no_prefilter_override_2024-05-28_2026-04-21.json"
        ),
        "execution_matrix": load_execution_matrix_evidence(root),
        "exit_walk_forward": _load_optional_json(
            report_dir / f"exit-parameter-walk-forward-{source_date}" / "summary.json"
        ),
        "market_state_guard_walk_forward": _load_optional_json(
            report_dir / f"market-state-guard-walk-forward-{source_date}" / "summary.json"
        ),
        "focus_parameter_walk_forward": _load_optional_json(
            report_dir / f"focus-strategy-parameter-walk-forward-{source_date}" / "summary.json"
        ),
        "profile_summary": _load_optional_json(
            report_dir / f"strategy-24m-profile-{source_date}.json"
        ),
    }


def _index_by(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(item.get(key)): item for item in items}


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _load_json(path)


def _extract_suggestion(strategy_key: str, suggestions: list[dict[str, Any]]) -> dict[str, Any]:
    for suggestion in suggestions:
        if suggestion.get("strategy_key") == strategy_key:
            return suggestion
    return {}


def _metrics(item: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "sample_count", "filled_count", "unfilled_count", "unfilled_rate_pct",
        "total_return_pct", "annualized_return_pct", "max_drawdown_pct",
        "sharpe_ratio", "win_rate_pct", "profit_loss_ratio", "profit_factor",
        "avg_trade_return_pct", "stop_loss_rate_pct", "avg_holding_days",
        "median_holding_days", "consecutive_loss_count", "max_single_loss_pct",
        "max_single_gain_pct", "signal_state_counts", "confirmed_only_metrics",
    ]
    metrics = {field: item.get(field) for field in fields}
    metrics["trade_count"] = item.get("filled_count")
    metrics.update(_trade_extremes_or_missing(metrics))
    metrics.update(_sample_split_metrics(item))
    return metrics


def _missing_metric(reason: str) -> dict[str, Any]:
    return {
        "status": "not_available_in_existing_24m_strategy_report",
        "required_before_production": True,
        "reason": reason,
    }


def _trade_extremes_or_missing(metrics: dict[str, Any]) -> dict[str, Any]:
    required = ("consecutive_loss_count", "max_single_loss_pct", "max_single_gain_pct")
    return {} if all(metrics.get(key) is not None for key in required) else _missing_trade_extremes()


def _missing_trade_extremes() -> dict[str, Any]:
    reason = "底层聚合报告未输出逐笔交易序列，不能可靠计算。"
    return {
        "consecutive_loss_count": _missing_metric(reason),
        "max_single_loss_pct": _missing_metric(reason),
        "max_single_gain_pct": _missing_metric(reason),
    }


def _sample_split_metrics(item: dict[str, Any]) -> dict[str, Any]:
    quarters = item.get("quarter_breakdown", []) or []
    return {
        "in_sample_performance": {
            "status": "baseline_quarter_proxy_only_not_candidate_optimization",
            "quarters": quarters[:-1],
            "note": "现有报告只有全量参数的季度切片，不等同于候选参数样本内优化结果。",
        },
        "out_of_sample_performance": {
            "status": "latest_quarter_proxy_only_not_walk_forward_candidate",
            "quarter": quarters[-1] if quarters else None,
            "note": "候选参数尚未完成 walk-forward 样本外重跑。",
        },
    }


def _risk_flags(strategy: dict[str, Any], governance: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    sample_count = int(strategy.get("sample_count") or 0)
    pf = float(strategy.get("profit_factor") or 0)
    avg_return = float(strategy.get("avg_trade_return_pct") or 0)
    max_drawdown = float(strategy.get("max_drawdown_pct") or 0)
    if sample_count < 300:
        flags.append("low_sample_count")
    if pf < 1:
        flags.append("profit_factor_below_1")
    if avg_return <= 0:
        flags.append("non_positive_avg_trade_return")
    if max_drawdown <= -50:
        flags.append("max_drawdown_over_50pct")
    if governance.get("parameter_grid_allowed") is False:
        flags.append("parameter_grid_not_allowed")
    return flags


def _overfit_level(flags: list[str], recommendation: str) -> str:
    if "profit_factor_below_1" in flags or "non_positive_avg_trade_return" in flags:
        return "high"
    if "low_sample_count" in flags and recommendation != "pause_or_downgrade":
        return "medium_high"
    if "max_drawdown_over_50pct" in flags:
        return "medium_high"
    return "medium"


def _recommendation(
    strategy: dict[str, Any],
    governance: dict[str, Any],
    layer: str,
) -> str:
    strategy_key = str(strategy.get("strategy_key"))
    pf = float(strategy.get("profit_factor") or 0)
    avg_return = float(strategy.get("avg_trade_return_pct") or 0)
    max_drawdown = float(strategy.get("max_drawdown_pct") or 0)
    action = str(governance.get("recommended_action") or "")
    if "pause" in action or pf < 1 or avg_return <= 0:
        return "pause_or_downgrade"
    if strategy_key == "deep_pullback":
        return "paper_observe_candidate"
    if layer == "production" and max_drawdown <= -50:
        return "retain_but_reduce_weight_and_add_constraints"
    if layer == "production":
        return "retain_current_layer"
    if pf >= 1.2 and avg_return > 0:
        return "retain_research_or_shadow"
    return "downgrade_to_factor_or_research_only"


def _production_params(strategy_key: str) -> dict[str, Any]:
    prefilter = LOW_BUY_STRATEGY_PREFILTER_DEFAULTS.get(strategy_key, {})
    execution = LOW_BUY_STRATEGY_EXECUTION_DEFAULTS.get(strategy_key, {})
    return {
        "prefilter": dict(prefilter),
        "execution": dict(execution),
    }


def _related_metrics(related_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in related_report.get("strategies", []) or []:
        indexed[str(item.get("strategy"))] = {
            "sample_count": item.get("sample_count"),
            "filled_count": item.get("filled_count"),
            "confirmed_count": item.get("confirmed_count"),
            "near_entry_count": item.get("near_entry_count"),
            "win_rate_pct": item.get("win_rate_pct"),
            "profit_factor": item.get("profit_factor"),
            "avg_return_pct": item.get("avg_return_pct"),
            "max_drawdown_pct": item.get("max_drawdown_pct"),
            "stop_loss_rate_pct": item.get("stop_loss_rate_pct"),
            "status": item.get("status"),
        }
    return indexed


def _build_strategy_items(sources: dict[str, Any]) -> list[dict[str, Any]]:
    strategy_24m = sources["strategy_24m"]
    closed_loop = sources["closed_loop"]
    governance_by_key = _index_by(closed_loop["strategy_governance"]["items"], "strategy_key")
    suggestions = strategy_24m.get("parameter_adjustment_suggestions", []) or []
    related_by_key = _related_metrics(sources["related_strategy"])
    items: list[dict[str, Any]] = []
    for strategy in strategy_24m.get("all_strategies", []) or []:
        key = str(strategy["strategy_key"])
        governance = governance_by_key.get(key, {})
        layer = strategy_layer(key)
        tier = get_strategy_tier(key).value
        recommendation = _recommendation(strategy, governance, layer)
        flags = _risk_flags(strategy, governance)
        original = _production_params(key)
        suggestion = _extract_suggestion(key, suggestions)
        param_plan = candidate_param_plan(
            original=original,
            governance=governance,
            suggestion=suggestion,
        )
        before = _metrics(strategy)
        signal_diagnosis = buy_signal_diagnosis(
            strategy_key=key,
            layer=layer,
            strong_buy_paused=strong_buy_paused(key),
            metrics=before,
        )
        sector_breakdown = sector_breakdown_or_missing(strategy)
        wf_matrix = walk_forward_matrix(
            strategy_key=key,
            governance=governance,
            walk_forward=sources["closed_loop"].get("walk_forward", {}),
            recommendation=recommendation,
        )
        after = dict(before)
        after.update(
            {
                "status": "not_recomputed_no_candidate_promoted",
                "verified_improvement": False,
                "reason": "本轮不把回测搜索结果直接当作优化后收益；候选参数尚未完成 walk-forward 和 Shadow。",
            }
        )
        items.append(
            {
                "strategy_key": key,
                "strategy_title": strategy.get("strategy_title"),
                "strategy_family": strategy.get("strategy_family"),
                "policy_layer": layer,
                "policy_tier": tier,
                "strong_buy_paused": strong_buy_paused(key),
                "governance_state": governance.get("governance_state"),
                "recommended_action_from_governance": governance.get("recommended_action"),
                "review_recommendation": recommendation,
                "original_parameters": original,
                "optimized_parameters": param_plan,
                "changed_parameters": param_plan["candidate_overrides_for_shadow_or_walk_forward"],
                "change_reason": suggestion.get("reason") or governance.get("recommended_action"),
                "before_metrics": before,
                "after_metrics": after,
                "buy_signal_diagnosis": signal_diagnosis,
                "missing_required_metrics": missing_required_metrics(
                    before, sector_breakdown, wf_matrix
                ),
                "related_capital_limited_metrics": related_by_key.get(key),
                "market_state_breakdown": strategy.get("market_state_breakdown", []),
                "quarter_breakdown": strategy.get("quarter_breakdown", []),
                "sector_breakdown": sector_breakdown,
                "walk_forward_validation": wf_matrix,
                "purged_gap_validation": {
                    "candidate_passed": wf_matrix["purged_gap_passed"],
                    "status": "planned_not_executed_for_strategy_parameter_candidates",
                    "purged_gap_days": wf_matrix["purged_gap_days"],
                    "required_before_production": True,
                },
                "future_function_risk": {
                    "status": sources["closed_loop"].get("temporal_guard", {}).get("status"),
                    "risk_level": "low_for_existing_report_generation",
                    "open_risk": "候选参数尚未完成带 purged gap 的时序复验。",
                },
                "overfit_flags": flags,
                "overfit_risk_level": _overfit_level(flags, recommendation),
            }
        )
    return items


def _decision_lists(strategy_items: list[dict[str, Any]]) -> dict[str, list[str]]:
    decisions = {
        "retain_current_layer": [],
        "downgrade_or_reduce_weight": [],
        "pause": [],
        "promote_to_production": [],
        "paper_or_shadow_observe": [],
    }
    for item in strategy_items:
        key = item["strategy_key"]
        recommendation = item["review_recommendation"]
        if recommendation in {"retain_current_layer", "retain_research_or_shadow"}:
            decisions["retain_current_layer"].append(key)
        elif recommendation == "paper_observe_candidate":
            decisions["paper_or_shadow_observe"].append(key)
        elif recommendation == "pause_or_downgrade":
            decisions["pause"].append(key)
        else:
            decisions["downgrade_or_reduce_weight"].append(key)
    return decisions


def _strategy_family_summary(strategy_24m: dict[str, Any]) -> dict[str, Any]:
    summary = strategy_24m.get("strategy_family_summary") or {}
    if summary.get("time_series_splits"):
        return summary
    return strategy_family_summary(
        strategy_24m.get("all_strategies") or [],
        strategy_24m.get("performance_by_family") or [],
        strategy_24m.get("parameter_adjustment_suggestions") or [],
    )


def build_report(
    report_date: str | None = None,
    source_date: str = SOURCE_DATE,
    root: Path = ROOT,
) -> dict[str, Any]:
    report_date = report_date or date.today().isoformat()
    sources = _read_sources(root, source_date)
    strategy_items = _build_strategy_items(sources)
    closed_loop = sources["closed_loop"]
    strategy_24m = sources["strategy_24m"]
    gates = closed_loop.get("gates", [])
    blocking_gates = blocking_data_gates(gates)
    decisions = _decision_lists(strategy_items)
    return {
        "title": "策略模型与相关策略24个月优化审查报告",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "report_date": report_date,
        "source_date": source_date,
        "source_files": {
            "strategy_24m": f"docs/reports/strategy-24m-backtest-{source_date}.json",
            "closed_loop": f"docs/reports/strategy-improvement-closed-loop-{source_date}.json",
            "main_force": f"docs/reports/main-force-model-production-readiness-{source_date}.json",
            "related_strategy": (
                f"docs/reports/main-force-related-strategy-backtest-{source_date}/"
                "low_buy_market_backtest_24m_all_states_default_exit_no_guard_no_prefilter_override_2024-05-28_2026-04-21.json"
            ),
        },
        "scope": {
            "strategy_count": len(strategy_items),
            "strategy_keys": [item["strategy_key"] for item in strategy_items],
            "actual_evaluation_window": strategy_24m.get("scope", {}).get("actual_evaluation_window"),
            "data_coverage": strategy_24m.get("coverage"),
        },
        "executive_conclusion": {
            "can_connect_to_production_chain": False,
            "production_parameter_change_allowed": False,
            "reason": (
                "日线策略已有24个月研究基线，但 ETF 分钟线、成交元数据、Shadow 样本、"
                "候选参数 walk-forward/purged gap 均未闭环；新增模型只能进入只读 Shadow 或研究观察。"
            ),
            "blocking_gates": blocking_gates,
        },
        "strategy_decisions": decisions,
        "scope_coverage": scope_coverage(sources),
        "strategy_family_summary": _strategy_family_summary(strategy_24m),
        "strategy_items": strategy_items,
        "strategy_governance_summary": closed_loop.get("strategy_governance", {}).get("state_counts"),
        "walk_forward_policy": closed_loop.get("walk_forward"),
        "controlled_parameter_policy": closed_loop.get("controlled_parameter_policy"),
        "temporal_guard": closed_loop.get("temporal_guard"),
        "metric_interpretation_policy": {
            "production_promotion_metrics": [
                "net_return_pct",
                "profit_factor",
                "max_drawdown_pct",
                "stop_loss_rate_pct",
                "paper_account_equity_curve",
            ],
            "research_only_metrics": {
                "spike_return_*": (
                    "使用信号后未来窗口最高价，只能观察冲高机会，不能作为可成交收益或生产晋级依据。"
                ),
                "diagnostic_compound_return_pct": (
                    "逐成交信号连续复利诊断字段，不是真实资金曲线。"
                ),
            },
            "capital_curve_caveat": (
                "total_return_pct 已改为每日信号等权资金约束口径，但仍未覆盖现金、持仓上限、"
                "并发仓位、滑点和排队成交，生产前必须补真实 Paper 账户曲线。"
            ),
        },
        "models": model_reviews(sources),
        "exit_parameter_shadow_evidence": sources.get("execution_matrix", {}),
        "exit_parameter_walk_forward": sources.get("exit_walk_forward", {}),
        "market_state_guard_walk_forward": sources.get("market_state_guard_walk_forward", {}),
        "focus_parameter_walk_forward": sources.get("focus_parameter_walk_forward", {}),
        "data_gates": {
            "gates": gates,
            "etf_t0": strategy_24m.get("etf_t0"),
            "sector_etf_t0": strategy_24m.get("sector_etf_t0"),
            "smart_t": strategy_24m.get("smart_t"),
            "known_gaps": strategy_24m.get("data_and_test_gaps"),
        },
        "acceleration": acceleration_summary(sources.get("profile_summary", {})),
        "performance_profile": sources.get("profile_summary", {}),
        "tests": {
            "planned_commands": [
                "PYTHONPATH=. python scripts/generate_strategy_24m_optimization_report.py --date 2026-05-28",
                "DATABASE_URL=sqlite:///backend/data/t_quant.db PYTHONPATH=backend backend/.venv/bin/python backend/scripts/strategy_24m_backtest_report.py --json-output /tmp/strategy-24m-full-probe.json --markdown-output /tmp/strategy-24m-full-probe.md",
                "PYTHONPATH=. backend/.venv/bin/python -m pytest -q backend/tests/test_strategy_24m_optimization_report.py",
                "PYTHONPATH=. backend/.venv/bin/python -m pytest -q backend/tests/test_low_buy_backtest_isolation.py -k trade_extremes",
            ],
            "results": [],
        },
        "unfinished_items": unfinished_items(strategy_items),
    }

def write_report(report: dict[str, Any], root: Path = ROOT) -> tuple[Path, Path]:
    report_dir = root / "docs" / "reports"
    report_date = report["report_date"]
    json_path = report_dir / f"strategy-24m-optimization-report-{report_date}.json"
    md_path = report_dir / f"strategy-24m-optimization-report-{report_date}.md"
    _write_json(json_path, report)
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return md_path, json_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat(), help="output report date")
    parser.add_argument("--source-date", default=SOURCE_DATE, help="source report date")
    parser.add_argument(
        "--test-result",
        action="append",
        default=[],
        help="append a verification result summary to the generated report",
    )
    args = parser.parse_args()
    report = build_report(report_date=args.date, source_date=args.source_date)
    if args.test_result:
        report["tests"]["results"] = [
            {"status": "pass", "summary": result} for result in args.test_result
        ]
    md_path, json_path = write_report(report)
    print(f"wrote {md_path}")
    print(f"wrote {json_path}")


if __name__ == "__main__":
    main()
