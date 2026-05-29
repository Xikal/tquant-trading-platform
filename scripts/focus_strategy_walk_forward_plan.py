#!/usr/bin/env python3
"""Build a focused walk-forward evidence plan for priority strategies."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any


REPORT_DATE = "2026-05-28"
FOCUS_STRATEGIES = (
    "first_board",
    "volume_shrink",
    "late_session_strong_support",
    "core_midcap_vwap_ma5_retrace",
    "ma_channel_band",
    "leader_pullback_band",
)


def build_report(root: Path) -> dict[str, Any]:
    source = root / "docs" / "reports" / f"market-state-guard-walk-forward-{REPORT_DATE}"
    windows = _collect_windows(source / "windows")
    rows = [_strategy_summary(strategy, windows) for strategy in FOCUS_STRATEGIES]
    return {
        "title": "6 个重点策略窄口径 walk-forward 执行清单",
        "report_date": REPORT_DATE,
        "source": str(source.relative_to(root)),
        "scope": {
            "strategy_keys": list(FOCUS_STRATEGIES),
            "window_count": len(windows),
            "evidence_reused": "market_state_guard_7_oos_windows",
            "new_backtest_started": False,
        },
        "rules": {
            "no_production_param_write": True,
            "random_split_allowed": False,
            "purged_gap_days": 10,
            "candidate_grid_policy": "2-3 trading-logic variants per strategy, not full brute force.",
        },
        "strategies": rows,
        "next_execution_order": _next_order(rows),
        "remaining_blockers": [
            "strategy_parameter_variants_not_recomputed_yet",
            "full_purged_gap_candidate_grid_not_executed_yet",
            "shadow_settled_sample_not_accumulated",
        ],
    }


def write_report(report: dict[str, Any], root: Path) -> tuple[Path, Path]:
    out_dir = root / "docs" / "reports" / f"focus-strategy-walk-forward-plan-{REPORT_DATE}"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "summary.json"
    md_path = out_dir / "summary.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    return json_path, md_path


def _collect_windows(path: Path) -> list[dict[str, Any]]:
    current = sorted((path / "current").glob("*.json"))
    guard = sorted((path / "block_retreat").glob("*.json"))
    windows: list[dict[str, Any]] = []
    for index, (current_path, guard_path) in enumerate(zip(current, guard), start=1):
        windows.append(
            {
                "window_id": index,
                "current": _load_json(current_path),
                "block_retreat": _load_json(guard_path),
                "current_path": current_path,
                "guard_path": guard_path,
            }
        )
    return windows


def _strategy_summary(strategy: str, windows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for window in windows:
        current = _strategy_row(window["current"], strategy)
        guard = _strategy_row(window["block_retreat"], strategy)
        rows.append(_window_metrics(window["window_id"], current, guard))
    return {
        "strategy_key": strategy,
        "window_count": len(rows),
        "windows_with_confirmed_trades": sum(1 for row in rows if row["current"]["trade_count"] > 0),
        "avg_current_profit_factor": _avg(row["current"]["profit_factor"] for row in rows),
        "avg_current_max_drawdown_pct": _avg(row["current"]["max_drawdown_pct"] for row in rows),
        "avg_guard_profit_factor_delta": _avg(row["delta"]["profit_factor"] for row in rows),
        "avg_guard_drawdown_delta_pct": _avg(row["delta"]["max_drawdown_pct"] for row in rows),
        "recommended_candidate_variants": _candidate_variants(strategy),
        "execution_priority": _priority(strategy, rows),
        "production_eligible": False,
        "shadow_only": True,
        "windows": rows,
    }


def _window_metrics(window_id: int, current: dict[str, Any], guard: dict[str, Any]) -> dict[str, Any]:
    return {
        "window_id": window_id,
        "current": current,
        "block_retreat": guard,
        "delta": {
            "profit_factor": _round(guard["profit_factor"] - current["profit_factor"]),
            "max_drawdown_pct": _round(guard["max_drawdown_pct"] - current["max_drawdown_pct"]),
            "trade_count": guard["trade_count"] - current["trade_count"],
        },
    }


def _strategy_row(report: dict[str, Any], strategy: str) -> dict[str, Any]:
    row = next((item for item in report.get("strategies", []) if item.get("strategy_key") == strategy), {})
    result = row.get("confirmed_result") or {}
    perf = result.get("performance") or {}
    return {
        "trade_count": int(perf.get("trade_count") or result.get("filled_count") or 0),
        "win_rate_pct": _round(perf.get("win_rate_pct") or result.get("net_win_rate") or 0.0),
        "avg_trade_return_pct": _round(perf.get("avg_net_return_pct") or result.get("avg_net_return_pct") or 0.0),
        "profit_factor": _round(perf.get("profit_factor") or result.get("execution_profit_factor") or 0.0),
        "max_drawdown_pct": _round(perf.get("max_drawdown_pct") or 0.0),
        "stop_loss_rate_pct": _round(perf.get("stop_loss_rate_pct") or result.get("stop_loss_rate") or 0.0),
        "total_return_pct": _round(perf.get("total_return_pct") or 0.0),
    }


def _candidate_variants(strategy: str) -> list[dict[str, Any]]:
    variants = {
        "first_board": [
            {"name": "current_exit_plus_block_retreat", "params": {"market_guard": "block_retreat"}},
            {"name": "quick_tp3_trailing1", "params": {"first_take_profit_pct": 3.0, "trailing_stop_pct": 1.0, "max_holding_days": 3}},
        ],
        "volume_shrink": [
            {"name": "quick_tp3_trailing1", "params": {"first_take_profit_pct": 3.0, "trailing_stop_pct": 1.0, "max_holding_days": 3}},
            {"name": "tight_distribution", "params": {"max_distribution_risk_score_delta": -0.3}},
        ],
        "late_session_strong_support": [
            {"name": "raise_min_score", "params": {"min_score_delta": 3}},
            {"name": "quick_tp3_trailing1", "params": {"first_take_profit_pct": 3.0, "trailing_stop_pct": 1.0, "max_holding_days": 3}},
        ],
        "core_midcap_vwap_ma5_retrace": [
            {"name": "raise_min_score", "params": {"min_score_delta": 3}},
            {"name": "tight_ma_distance", "params": {"max_ma_distance_pct_delta": -0.2}},
        ],
        "ma_channel_band": [
            {"name": "mapped_distribution_tighten", "params": {"max_distribution_risk_score_delta": -0.3}},
            {"name": "raise_min_score", "params": {"min_score_delta": 3}},
        ],
        "leader_pullback_band": [
            {"name": "mapped_distribution_tighten", "params": {"max_distribution_risk_score_delta": -0.3}},
            {"name": "support_distance_tighten", "params": {"max_support_distance_pct_delta": -0.3}},
        ],
    }
    return variants[strategy]


def _priority(strategy: str, rows: list[dict[str, Any]]) -> str:
    trade_windows = sum(1 for row in rows if row["current"]["trade_count"] > 0)
    avg_pf = _avg(row["current"]["profit_factor"] for row in rows)
    if trade_windows == 0:
        return "shadow_signal_gate_first"
    if strategy in {"first_board", "volume_shrink"} and avg_pf >= 1.0:
        return "run_candidate_grid_first"
    return "run_after_core_or_keep_research"


def _next_order(rows: list[dict[str, Any]]) -> list[str]:
    rank = {"run_candidate_grid_first": 0, "run_after_core_or_keep_research": 1, "shadow_signal_gate_first": 2}
    return [row["strategy_key"] for row in sorted(rows, key=lambda row: rank[row["execution_priority"]])]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _avg(values) -> float:
    items = [float(value or 0.0) for value in values]
    return _round(mean(items)) if items else 0.0


def _round(value: Any) -> float:
    return round(float(value or 0.0), 4)


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [f"# {report['title']}", "", f"- 报告日期：{report['report_date']}", f"- 来源：{report['source']}"]
    lines.append(f"- 新启动回测：{'是' if report['scope']['new_backtest_started'] else '否'}")
    lines.append("")
    lines.append("| 策略 | 确认成交窗口 | 平均 PF | 平均回撤 | 保护 PF 差 | 优先级 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | --- |")
    for row in report["strategies"]:
        lines.append(
            f"| {row['strategy_key']} | {row['windows_with_confirmed_trades']}/{row['window_count']} | "
            f"{row['avg_current_profit_factor']} | {row['avg_current_max_drawdown_pct']} | "
            f"{row['avg_guard_profit_factor_delta']} | {row['execution_priority']} |"
        )
    lines.append("")
    lines.append(f"- 下一步执行顺序：{', '.join(report['next_execution_order'])}")
    lines.append(f"- 剩余阻断：{', '.join(report['remaining_blockers'])}")
    return "\n".join(lines) + "\n"


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    report = build_report(root)
    json_path, md_path = write_report(report, root)
    print(json.dumps({"json": str(json_path), "markdown": str(md_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
