from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKTEST_SCRIPT = ROOT_DIR / "backend" / "scripts" / "low_buy_market_backtest.py"
DEFAULT_THRESHOLDS = (5.8, 5.5, 5.2, 5.0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="首板出货风险阈值研究矩阵")
    parser.add_argument("--months", type=int, default=24)
    parser.add_argument("--start", default="")
    parser.add_argument("--end", default="")
    parser.add_argument("--states", default="confirmed")
    parser.add_argument("--scan-limit", type=int, default=480)
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--target-profit-pct", type=float, default=3.0)
    parser.add_argument("--forward-days", type=int, default=5)
    parser.add_argument("--max-dates", type=int, default=0)
    parser.add_argument("--engine", choices=("fast", "legacy"), default="fast")
    parser.add_argument("--materialization-mode", choices=("isolated", "production", "read-only"), default="isolated")
    parser.add_argument("--thresholds", default=",".join(f"{item:g}" for item in DEFAULT_THRESHOLDS))
    parser.add_argument("--output-dir", default=str(ROOT_DIR / "backend" / "data" / "reports" / "first_board_distribution_matrix"))
    parser.add_argument("--matrix-output-dir", default=str(ROOT_DIR / "backend" / "data" / "reports" / "first_board_distribution_matrix"))
    parser.add_argument("--python", default=sys.executable)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    thresholds = _resolve_thresholds(args.thresholds)
    output_dir = Path(args.output_dir)
    matrix_output_dir = Path(args.matrix_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    matrix_output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for threshold in thresholds:
        payload = _run_threshold(args=args, threshold=threshold, output_dir=output_dir)
        rows.append(_matrix_row(threshold=threshold, payload=payload))

    report = _build_report(args=args, rows=rows)
    stem = _matrix_stem(args)
    json_path = matrix_output_dir / f"{stem}.json"
    md_path = matrix_output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "threshold_count": len(rows)}, ensure_ascii=False, indent=2))
    return 0


def _resolve_thresholds(raw: str) -> list[float]:
    values: list[float] = []
    for item in str(raw or "").split(","):
        text = item.strip()
        if not text:
            continue
        try:
            values.append(float(text))
        except ValueError as exc:
            raise SystemExit(f"出货风险阈值不是数字: {text}") from exc
    if not values:
        raise SystemExit("至少需要一个出货风险阈值")
    return values


def _run_threshold(*, args: argparse.Namespace, threshold: float, output_dir: Path) -> dict[str, Any]:
    cmd = [
        args.python,
        str(BACKTEST_SCRIPT),
        "--months",
        str(args.months),
        "--strategies",
        "first_board",
        "--states",
        args.states,
        "--scan-limit",
        str(args.scan_limit),
        "--limit",
        str(args.limit),
        "--target-profit-pct",
        str(args.target_profit_pct),
        "--forward-days",
        str(args.forward_days),
        "--engine",
        args.engine,
        "--materialization-mode",
        args.materialization_mode,
        "--prefilter-override",
        f"first_board.max_distribution_risk_score={threshold:g}",
        "--output-dir",
        str(output_dir),
    ]
    if args.start:
        cmd.extend(["--start", args.start])
    if args.end:
        cmd.extend(["--end", args.end])
    if args.max_dates > 0:
        cmd.extend(["--max-dates", str(args.max_dates)])

    env = dict(os.environ)
    env["PYTHONPATH"] = _append_pythonpath(env.get("PYTHONPATH", ""), str(ROOT_DIR / "backend"), str(ROOT_DIR))
    print(f"[first-board-distribution] running threshold {threshold:g}: {' '.join(cmd)}", flush=True)
    completed = subprocess.run(cmd, cwd=ROOT_DIR, env=env, check=True, capture_output=True, text=True)
    result = _extract_json_output(completed.stdout)
    report_path = Path(result["json"])
    return json.loads(report_path.read_text(encoding="utf-8"))


def _extract_json_output(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start < 0 or end < start:
        raise SystemExit(f"回测输出不是 JSON: {stdout[-1000:]}")
    return json.loads(stdout[start : end + 1])


def _append_pythonpath(existing: str, *items: str) -> str:
    parts = [item for item in items if item]
    if existing:
        parts.append(existing)
    return os.pathsep.join(parts)


def _matrix_row(*, threshold: float, payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary", {})
    metrics = summary.get("backtest_metrics", {})
    total = summary.get("total_evaluated_result", {})
    confirmed = summary.get("confirmed_result", {})
    coverage = summary.get("data_coverage", {})
    signal_counts = summary.get("signal_state_counts", {})
    return {
        "threshold": threshold,
        "prefilter_overrides": summary.get("prefilter_overrides", ""),
        "evaluation_start": summary.get("evaluation_start", ""),
        "evaluation_end": summary.get("evaluation_end", ""),
        "coverage_pct": coverage.get("coverage_pct", 0.0),
        "coverage_status": coverage.get("status", "unknown"),
        "scanned_count": summary.get("scanned_count", 0),
        "matched_count": summary.get("matched_count", 0),
        "confirmed_count": summary.get("confirmed_count", 0),
        "near_entry_count": summary.get("near_entry_count", 0),
        "watch_count": signal_counts.get("watch", 0),
        "avoid_count": signal_counts.get("avoid", 0),
        "evaluated_count": total.get("evaluated_count", summary.get("evaluated_count", 0)),
        "filled_count": total.get("filled_count", summary.get("filled_count", 0)),
        "net_win_rate": total.get("net_win_rate", summary.get("net_win_rate", 0.0)),
        "avg_net_return_pct": total.get("avg_net_return_pct", summary.get("avg_net_return_pct", 0.0)),
        "stop_loss_rate": total.get("stop_loss_rate", summary.get("stop_loss_rate", 0.0)),
        "execution_profit_factor": total.get("execution_profit_factor", 0.0),
        "total_return_pct": metrics.get("total_return_pct", 0.0),
        "annualized_return_pct": metrics.get("annualized_return_pct", 0.0),
        "max_drawdown_pct": metrics.get("max_drawdown_pct", 0.0),
        "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
        "profit_loss_ratio": metrics.get("profit_loss_ratio", 0.0),
        "profit_factor": metrics.get("profit_factor", 0.0),
        "avg_holding_days": metrics.get("avg_holding_days", 0.0),
        "drawdown_recovery_status": metrics.get("drawdown_recovery_status", ""),
        "t1_high_3_hit_rate": confirmed.get("t1_high_3_hit_rate", 0.0),
        "avg_t1_high_return_pct": confirmed.get("avg_t1_high_return_pct", 0.0),
        "avg_t1_close_return_pct": confirmed.get("avg_t1_close_return_pct", 0.0),
        "filled_exit_reason_counts": summary.get("filled_exit_reason_counts", {}),
    }


def _build_report(*, args: argparse.Namespace, rows: list[dict[str, Any]]) -> dict[str, Any]:
    baseline = next((row for row in rows if float(row["threshold"]) == 5.8), rows[0] if rows else {})
    return {
        "title": "首板出货风险阈值研究矩阵",
        "scope": {
            "months": args.months,
            "start": args.start,
            "end": args.end,
            "strategy": "first_board",
            "states": args.states,
            "scan_limit": args.scan_limit,
            "limit": args.limit,
            "forward_days": args.forward_days,
            "engine": args.engine,
            "materialization_mode": args.materialization_mode,
            "max_dates": args.max_dates,
            "thresholds": [row["threshold"] for row in rows],
        },
        "baseline_threshold": baseline.get("threshold"),
        "rows": [_row_with_baseline_delta(row, baseline) for row in rows],
        "best_by_profit_factor": _best_threshold(rows, "profit_factor"),
        "best_by_drawdown": _best_threshold(rows, "max_drawdown_pct"),
        "best_by_avg_net_return": _best_threshold(rows, "avg_net_return_pct"),
        "warning": _coverage_warning(rows),
        "notes": [
            "本报告只覆盖 first_board 预筛 max_distribution_risk_score 研究矩阵。",
            "矩阵通过研究态 prefilter override 运行，不修改生产默认参数。",
            "是否调整默认值必须同时看样本数、PF、最大回撤和非退潮样本流失，不能只看单次收益。",
        ],
    }


def _row_with_baseline_delta(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    baseline_matched = float(baseline.get("matched_count", 0) or 0)
    matched = float(row.get("matched_count", 0) or 0)
    result["matched_delta_vs_baseline"] = int(matched - baseline_matched)
    result["matched_retention_pct"] = round(matched / baseline_matched * 100.0, 3) if baseline_matched > 0 else 0.0
    result["pf_delta_vs_baseline"] = round(float(row.get("profit_factor", 0) or 0) - float(baseline.get("profit_factor", 0) or 0), 4)
    result["max_drawdown_delta_vs_baseline"] = round(float(row.get("max_drawdown_pct", 0) or 0) - float(baseline.get("max_drawdown_pct", 0) or 0), 4)
    return result


def _best_threshold(rows: list[dict[str, Any]], field: str, *, reverse: bool = True) -> float | None:
    if not rows:
        return None
    return float(sorted(rows, key=lambda item: float(item.get(field, 0.0) or 0.0), reverse=reverse)[0]["threshold"])


def _coverage_warning(rows: list[dict[str, Any]]) -> str:
    if any(str(row.get("coverage_status")) != "complete" for row in rows):
        return "至少一个矩阵报告数据覆盖不足 90%，只能作为部分区间研究基线，不能替代完整 24 个月验收。"
    return ""


def _matrix_stem(args: argparse.Namespace) -> str:
    start = args.start or "auto"
    end = args.end or "auto"
    suffix = f"_{args.max_dates}d" if args.max_dates > 0 else ""
    states = str(args.states or "all").replace(",", "_").replace("/", "_")
    return f"first_board_distribution_matrix_{args.months}m_{states}_{start}_{end}{suffix}"


def _render_markdown(report: dict[str, Any]) -> str:
    scope = report.get("scope", {})
    lines = [
        f"# {report.get('title', '首板出货风险阈值研究矩阵')}",
        "",
        "## 结论",
        "",
        f"- 范围：{scope.get('months')}个月，策略 `first_board`，信号状态 `{scope.get('states')}`，引擎 `{scope.get('engine')}`。",
        f"- 基准阈值：{report.get('baseline_threshold')}。",
        f"- Profit Factor 最优阈值：{report.get('best_by_profit_factor')}。",
        f"- 最大回撤最优阈值：{report.get('best_by_drawdown')}。",
        f"- 均净收益最优阈值：{report.get('best_by_avg_net_return')}。",
        *( [f"- 警告：{report['warning']}"] if report.get("warning") else [] ),
        "",
        "## 矩阵结果",
        "",
        "| 阈值 | 命中候选 | 候选保留 | 确定买入 | 成交 | 净胜率 | 均净收益 | 止损率 | 执行PF | 总收益 | 最大回撤 | Sharpe | 盈亏比 | PF | 平均持仓 | 覆盖率 | 退出原因 |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in report.get("rows", []):
        lines.append(
            "| {threshold:g} | {matched} ({delta:+d}) | {retention}% | {confirmed} | {filled} | {win}% | {avg}% | {stop}% | {epf} | {total}% | {dd}% | {sharpe} | {pl} | {pf} | {hold} | {coverage}% | {reasons} |".format(
                threshold=float(row.get("threshold", 0.0) or 0.0),
                matched=int(row.get("matched_count", 0) or 0),
                delta=int(row.get("matched_delta_vs_baseline", 0) or 0),
                retention=row.get("matched_retention_pct", 0.0),
                confirmed=row.get("confirmed_count", 0),
                filled=row.get("filled_count", 0),
                win=row.get("net_win_rate", 0.0),
                avg=row.get("avg_net_return_pct", 0.0),
                stop=row.get("stop_loss_rate", 0.0),
                epf=row.get("execution_profit_factor", 0.0),
                total=row.get("total_return_pct", 0.0),
                dd=row.get("max_drawdown_pct", 0.0),
                sharpe=row.get("sharpe_ratio", 0.0),
                pl=row.get("profit_loss_ratio", 0.0),
                pf=row.get("profit_factor", 0.0),
                hold=row.get("avg_holding_days", 0.0),
                coverage=row.get("coverage_pct", 0.0),
                reasons=_render_counts(row.get("filled_exit_reason_counts", {})),
            )
        )
    lines.extend(["", "## 说明", ""])
    lines.extend(f"- {item}" for item in report.get("notes", []))
    return "\n".join(lines) + "\n"


def _render_counts(values: dict[str, int] | None, *, limit: int = 4) -> str:
    rows = list((values or {}).items())
    if not rows:
        return "-"
    head = [f"{key}: {value}" for key, value in rows[:limit]]
    if len(rows) > limit:
        head.append(f"其余 {len(rows) - limit} 项")
    return "；".join(head)


if __name__ == "__main__":
    raise SystemExit(main())
