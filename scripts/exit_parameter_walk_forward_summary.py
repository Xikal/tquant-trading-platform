#!/usr/bin/env python3
"""Summarize exit-parameter walk-forward matrix windows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DATE = "2026-05-28"


def build_summary(report_date: str = REPORT_DATE, root: Path = ROOT) -> dict[str, Any]:
    base = root / "docs" / "reports" / f"exit-parameter-walk-forward-{report_date}"
    rows = [_window_row(path) for path in sorted((base / "windows").glob("*.json"))]
    pass_rows = [row for row in rows if row["quick_tp3_trailing1"]["pass_vs_default"]]
    return {
        "title": "止盈止损辅助模型 walk-forward 实算摘要",
        "report_date": report_date,
        "source_dir": f"docs/reports/exit-parameter-walk-forward-{report_date}/windows",
        "variant_under_test": "quick_tp3_trailing1",
        "baseline_variant": "default_exit",
        "window_count": len(rows),
        "passed_window_count": len(pass_rows),
        "pass_rate_pct": _round(len(pass_rows) / max(len(rows), 1) * 100),
        "production_eligible": False,
        "shadow_candidate": len(rows) > 0 and len(pass_rows) == len(rows),
        "hard_stop_override_allowed": False,
        "promotion_blockers": [
            "online_shadow_settled_sample_lt_required",
            "full_strategy_parameter_grid_not_executed",
            "hard_stop_must_not_be_removed_or_loosened",
        ],
        "criteria": {
            "pass_vs_default": "quick PF > default PF and quick max drawdown is less negative than default.",
            "production": "Even if all windows pass, only Shadow is allowed until online settled samples pass gates.",
        },
        "windows": rows,
        "aggregate_delta": _aggregate_delta(rows),
    }


def write_summary(payload: dict[str, Any], root: Path = ROOT) -> tuple[Path, Path]:
    base = root / "docs" / "reports" / f"exit-parameter-walk-forward-{payload['report_date']}"
    json_path = base / "summary.json"
    md_path = base / "summary.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return md_path, json_path


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {payload['title']}",
        "",
        f"- 窗口数：{payload['window_count']}",
        f"- 通过窗口：{payload['passed_window_count']} / {payload['window_count']}，通过率 {payload['pass_rate_pct']}%",
        f"- Shadow 候选：{'是' if payload['shadow_candidate'] else '否'}",
        f"- 生产可用：{'是' if payload['production_eligible'] else '否'}",
        f"- 阻断：{', '.join(payload['promotion_blockers'])}",
        "",
        "| 窗口 | OOS | 基线 PF | 候选 PF | PF 改善 | 基线回撤 | 候选回撤 | 回撤改善 | 通过 |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in payload["windows"]:
        quick = row["quick_tp3_trailing1"]
        base = row["default_exit"]
        lines.append(
            f"| {row['window_id']} | {row['oos_start']}~{row['oos_end']} | "
            f"{base['profit_factor']} | {quick['profit_factor']} | {quick['delta_profit_factor']} | "
            f"{base['max_drawdown_pct']}% | {quick['max_drawdown_pct']}% | "
            f"{quick['delta_max_drawdown_pct']} | {'是' if quick['pass_vs_default'] else '否'} |"
        )
    return "\n".join(lines) + "\n"


def _window_row(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    scope = payload.get("scope", {})
    rows = {row["variant_key"]: row for row in payload.get("rows", [])}
    baseline = _variant_row(rows["default_exit"])
    quick = _variant_row(rows["quick_tp3_trailing1"], baseline)
    return {
        "window_id": _window_id(path),
        "source_path": str(path.relative_to(ROOT)),
        "oos_start": scope.get("start"),
        "oos_end": scope.get("end"),
        "default_exit": baseline,
        "quick_tp3_trailing1": quick,
    }


def _variant_row(row: dict[str, Any], baseline: dict[str, Any] | None = None) -> dict[str, Any]:
    result = {
        "profit_factor": _round(row.get("profit_factor")),
        "max_drawdown_pct": _round(row.get("max_drawdown_pct")),
        "total_return_pct": _round(row.get("total_return_pct")),
        "win_rate_pct": _round(row.get("net_win_rate")),
        "avg_trade_return_pct": _round(row.get("avg_net_return_pct")),
        "stop_loss_rate_pct": _round(row.get("stop_loss_rate")),
        "trade_count": int(row.get("filled_count") or 0),
    }
    if baseline:
        result["delta_profit_factor"] = _round(result["profit_factor"] - baseline["profit_factor"])
        result["delta_max_drawdown_pct"] = _round(result["max_drawdown_pct"] - baseline["max_drawdown_pct"])
        result["pass_vs_default"] = result["delta_profit_factor"] > 0 and result["delta_max_drawdown_pct"] > 0
    return result


def _aggregate_delta(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    return {
        "avg_delta_profit_factor": _round(sum(row["quick_tp3_trailing1"]["delta_profit_factor"] for row in rows) / len(rows)),
        "avg_delta_max_drawdown_pct": _round(sum(row["quick_tp3_trailing1"]["delta_max_drawdown_pct"] for row in rows) / len(rows)),
    }


def _window_id(path: Path) -> int:
    files = sorted(path.parent.glob("*.json"))
    return files.index(path) + 1


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
