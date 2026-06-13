from __future__ import annotations

import argparse
from pathlib import Path
from statistics import mean
from typing import Any, Mapping, Sequence


COHORTS = ["priority_top_n", "late_confirmed", "late_watch", "late_rejected"]
METRICS = [
    "sample_count",
    "avg_next_day_return",
    "hit_rate",
    "avg_max_gain",
    "avg_max_drawdown",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a local research report comparing priority board top N with "
            "late-session confirmation cohorts."
        )
    )
    parser.add_argument("--start-date", required=True, help="Inclusive trade date, YYYY-MM-DD.")
    parser.add_argument("--end-date", required=True, help="Inclusive trade date, YYYY-MM-DD.")
    parser.add_argument("--limit", type=int, default=12, help="Late-session board display limit.")
    parser.add_argument("--source-limit", type=int, default=30, help="Priority board source candidate limit.")
    parser.add_argument(
        "--output",
        default="docs/reports/late-session-board-backtest-local.md",
        help="Markdown report output path.",
    )
    return parser


def cohort_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, float | int]]:
    summary: dict[str, dict[str, float | int]] = {}
    for cohort in COHORTS:
        cohort_rows = [row for row in rows if row.get("cohort") == cohort]
        summary[cohort] = {
            "sample_count": len(cohort_rows),
            "avg_next_day_return": _avg(cohort_rows, "next_day_return"),
            "hit_rate": _hit_rate(cohort_rows),
            "avg_max_gain": _avg(cohort_rows, "max_gain"),
            "avg_max_drawdown": _avg(cohort_rows, "max_drawdown"),
        }
    return summary


def render_late_session_backtest_report(
    *,
    start_date: str,
    end_date: str,
    limit: int,
    source_limit: int,
    summary: Mapping[str, Mapping[str, float | int]],
) -> str:
    lines = [
        "# 尾盘推荐榜本地研究回测",
        "",
        f"- 样本区间：{start_date} 至 {end_date}",
        f"- 展示数量：{limit}",
        f"- priority board top N 来源数量：{source_limit}",
        "- 分组：priority board top N、late_confirmed、late_watch、late_rejected",
        "- 研究边界：max_gain / max_drawdown 仅用于机会与回撤观察，不能作为可交易收益。",
        "- 执行边界：脚本只生成本地研究报告，不写生产配置、不提交任务、不刷新榜单。",
        "",
        "## 分组指标",
        "",
        "| cohort | sample_count | avg_next_day_return | hit_rate | avg_max_gain | avg_max_drawdown |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for cohort in COHORTS:
        metrics = summary.get(cohort, {})
        lines.append(
            "| {cohort} | {sample_count} | {avg_next_day_return:.4f} | {hit_rate:.4f} | "
            "{avg_max_gain:.4f} | {avg_max_drawdown:.4f} |".format(
                cohort=cohort,
                sample_count=int(metrics.get("sample_count", 0)),
                avg_next_day_return=float(metrics.get("avg_next_day_return", 0.0)),
                hit_rate=float(metrics.get("hit_rate", 0.0)),
                avg_max_gain=float(metrics.get("avg_max_gain", 0.0)),
                avg_max_drawdown=float(metrics.get("avg_max_drawdown", 0.0)),
            )
        )
    lines.extend(
        [
            "",
            "## 后续接入点",
            "",
            "- 历史 priority board 快照读取。",
            "- 14:50、14:55、14:57 分钟线/VWAP 状态回放。",
            "- 次日开盘、最高、最低、收盘的结果归因。",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = cohort_summary([])
    report = render_late_session_backtest_report(
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit,
        source_limit=args.source_limit,
        summary=summary,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(f"wrote {output}")
    return 0


def _avg(rows: Sequence[Mapping[str, Any]], field: str) -> float:
    values = [float(row[field]) for row in rows if row.get(field) is not None]
    return mean(values) if values else 0.0


def _hit_rate(rows: Sequence[Mapping[str, Any]]) -> float:
    if not rows:
        return 0.0
    return sum(1 for row in rows if row.get("hit")) / len(rows)


if __name__ == "__main__":
    raise SystemExit(main())
