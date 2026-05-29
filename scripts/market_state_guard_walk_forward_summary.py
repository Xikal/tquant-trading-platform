#!/usr/bin/env python3
"""Summarize market-state guard walk-forward A/B windows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DATE = "2026-05-28"


def build_summary(report_date: str = REPORT_DATE, root: Path = ROOT) -> dict[str, Any]:
    base = root / "docs" / "reports" / f"market-state-guard-walk-forward-{report_date}"
    baseline_files = _json_files(base / "windows" / "current")
    guarded_files = _json_files(base / "windows" / "block_retreat")
    windows = [_window_row(index + 1, current, guarded) for index, (current, guarded) in enumerate(zip(baseline_files, guarded_files))]
    pass_rows = [row for row in windows if row["block_retreat"]["pass_vs_current"]]
    return {
        "title": "市场状态保护参数 walk-forward 实算摘要",
        "report_date": report_date,
        "source_dir": f"docs/reports/market-state-guard-walk-forward-{report_date}/windows",
        "parameter_under_test": "market_state_switch",
        "variant_under_test": "block_retreat",
        "baseline_variant": "current",
        "window_count": len(windows),
        "planned_window_count": 7,
        "completed_window_count": len(windows),
        "passed_window_count": len(pass_rows),
        "pass_rate_pct": _round(len(pass_rows) / max(len(windows), 1) * 100),
        "production_eligible": False,
        "shadow_candidate": False,
        "partial_evidence": len(windows) < 7,
        "promotion_blockers": _promotion_blockers(windows, pass_rows),
        "criteria": {
            "pass_vs_current": "block_retreat PF >= current PF, total return >= current, and max drawdown is not worse.",
            "production": "Must complete all 7 windows, pass stability checks, and remain Shadow-only before any production parameter change.",
        },
        "windows": windows,
        "aggregate_delta": _aggregate_delta(windows),
        "conclusion": _conclusion(windows, pass_rows),
    }


def write_summary(payload: dict[str, Any], root: Path = ROOT) -> tuple[Path, Path]:
    base = root / "docs" / "reports" / f"market-state-guard-walk-forward-{payload['report_date']}"
    json_path = base / "summary.json"
    md_path = base / "summary.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return md_path, json_path


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {payload['title']}",
        "",
        f"- 参数：{payload['parameter_under_test']}={payload['variant_under_test']}",
        f"- 已完成窗口：{payload['completed_window_count']} / {payload['planned_window_count']}",
        f"- 通过窗口：{payload['passed_window_count']} / {payload['window_count']}，通过率 {payload['pass_rate_pct']}%",
        f"- Shadow 候选：{'是' if payload['shadow_candidate'] else '否'}",
        f"- 生产可用：{'是' if payload['production_eligible'] else '否'}",
        f"- 结论：{payload['conclusion']}",
        f"- 阻断：{', '.join(payload['promotion_blockers'])}",
        "",
        "| 窗口 | OOS | 基线 PF | 阻断 PF | PF 差 | 基线收益 | 阻断收益 | 收益差 | 基线回撤 | 阻断回撤 | 回撤差 | 阻断数 | 通过 |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in payload["windows"]:
        base = row["current"]
        guard = row["block_retreat"]
        lines.append(
            f"| {row['window_id']} | {row['oos_start']}~{row['oos_end']} | "
            f"{base['profit_factor']} | {guard['profit_factor']} | {guard['delta_profit_factor']} | "
            f"{base['total_return_pct']}% | {guard['total_return_pct']}% | {guard['delta_total_return_pct']} | "
            f"{base['max_drawdown_pct']}% | {guard['max_drawdown_pct']}% | {guard['delta_max_drawdown_pct']} | "
            f"{guard['market_guard_count']} | {'是' if guard['pass_vs_current'] else '否'} |"
        )
    return "\n".join(lines) + "\n"


def _json_files(path: Path) -> list[Path]:
    return sorted(path.glob("*.json"))


def _window_row(window_id: int, current_path: Path, guarded_path: Path) -> dict[str, Any]:
    current = json.loads(current_path.read_text(encoding="utf-8"))
    guarded = json.loads(guarded_path.read_text(encoding="utf-8"))
    current_row = _metrics(current, source_path=current_path)
    guarded_row = _metrics(guarded, baseline=current_row, source_path=guarded_path)
    return {
        "window_id": window_id,
        "oos_start": current["summary"].get("evaluation_start"),
        "oos_end": current["summary"].get("evaluation_end"),
        "current": current_row,
        "block_retreat": guarded_row,
    }


def _metrics(
    payload: dict[str, Any],
    baseline: dict[str, Any] | None = None,
    *,
    source_path: Path,
) -> dict[str, Any]:
    summary = payload.get("summary", {})
    metrics = summary.get("backtest_metrics", {})
    row = {
        "source_path": str(source_path.relative_to(ROOT)),
        "evaluated_count": int(metrics.get("evaluated_count") or summary.get("evaluated_count") or 0),
        "trade_count": int(metrics.get("trade_count") or summary.get("filled_count") or 0),
        "profit_factor": _round(metrics.get("profit_factor")),
        "total_return_pct": _round(metrics.get("total_return_pct")),
        "max_drawdown_pct": _round(metrics.get("max_drawdown_pct")),
        "win_rate_pct": _round(metrics.get("win_rate_pct")),
        "avg_net_return_pct": _round(metrics.get("avg_net_return_pct")),
        "stop_loss_rate_pct": _round(summary.get("stop_loss_rate")),
        "market_guard_count": int(summary.get("market_guard_count") or 0),
    }
    if baseline:
        row.update(_delta(row, baseline))
    return row


def _delta(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    pf_delta = _round(row["profit_factor"] - baseline["profit_factor"])
    return_delta = _round(row["total_return_pct"] - baseline["total_return_pct"])
    drawdown_delta = _round(row["max_drawdown_pct"] - baseline["max_drawdown_pct"])
    return {
        "delta_profit_factor": pf_delta,
        "delta_total_return_pct": return_delta,
        "delta_max_drawdown_pct": drawdown_delta,
        "pass_vs_current": pf_delta >= 0 and return_delta >= 0 and drawdown_delta >= 0,
    }


def _aggregate_delta(windows: list[dict[str, Any]]) -> dict[str, Any]:
    if not windows:
        return {}
    return {
        "avg_delta_profit_factor": _avg("delta_profit_factor", windows),
        "avg_delta_total_return_pct": _avg("delta_total_return_pct", windows),
        "avg_delta_max_drawdown_pct": _avg("delta_max_drawdown_pct", windows),
        "total_market_guard_count": sum(row["block_retreat"]["market_guard_count"] for row in windows),
    }


def _avg(key: str, windows: list[dict[str, Any]]) -> float:
    return _round(sum(row["block_retreat"][key] for row in windows) / len(windows))


def _promotion_blockers(windows: list[dict[str, Any]], pass_rows: list[dict[str, Any]]) -> list[str]:
    blockers = ["production_param_write_from_backtest_forbidden"]
    if len(windows) < 7:
        blockers.append("market_state_guard_walk_forward_partial_windows")
    if len(pass_rows) < len(windows):
        blockers.append("market_state_guard_not_consistently_better_than_current")
    return blockers


def _conclusion(windows: list[dict[str, Any]], pass_rows: list[dict[str, Any]]) -> str:
    if not windows:
        return "没有可用窗口，不能评估。"
    if pass_rows:
        return "部分窗口有单项改善，但未稳定通过 PF/收益/回撤三项联合标准，不能写生产。"
    return "已完成窗口均未通过联合标准，block_retreat 不建议作为生产参数。"


def _round(value: Any) -> float:
    return round(float(value or 0.0), 4)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=REPORT_DATE)
    args = parser.parse_args()
    md_path, json_path = write_summary(build_summary(report_date=args.date))
    print(json.dumps({"markdown": str(md_path), "json": str(json_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
