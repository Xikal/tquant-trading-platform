from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_report(report: dict[str, Any], *, markdown_path: Path, json_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    window = report["window"]
    coverage = summary.get("sample_coverage") or {}
    coverage_text = ", ".join(f"{key}={value}" for key, value in coverage.items()) or "无"
    missing_buckets = summary.get("missing_sample_buckets") or []
    missing_text = ", ".join(missing_buckets) or "无"
    lines = [
        "# 集合竞价 Provider Spike 报告",
        "",
        f"- 生成时间：`{report['generated_at']}`",
        f"- 数据源：`{report['source']}`",
        f"- 状态：`{report['status']}`",
        f"- 结论：`{report['conclusion']}`",
        f"- 说明：{report['message']}",
        "",
        "## 窗口",
        "",
        f"- 交易日：`{window['trade_date']}`",
        f"- 检查时间：`{window['checked_at']}`",
        f"- 是否交易日：`{window['is_trading_day']}`",
        f"- 是否在 spike 窗口：`{window['in_window']}`",
        f"- 窗口：`{window['window_start']}` - `{window['window_end']}`",
        "",
        "## 样本与字段",
        "",
        f"- 样本数：`{summary['sample_size']}`",
        f"- 样本覆盖：`{coverage_text}`",
        f"- 缺失覆盖：`{missing_text}`",
        f"- 调用数：`{summary['called_count']}`",
        f"- 可用数：`{summary['usable_count']}`",
        f"- 失败率：`{summary['failure_rate']}`",
        f"- 有 9:20-9:25 过程行的标的数：`{summary['process_symbols']}`",
        f"- 有 9:25 结果行的标的数：`{summary['result_symbols']}`",
        f"- 字段并集：`{', '.join(summary['fields']) or '无'}`",
        "",
        "## 后续决策",
        "",
        f"- G2 允许：`{report['phase_decision']['g2_allowed']}`",
        f"- G4 允许：`{report['phase_decision']['g4_allowed']}`",
        "",
        "## 明细",
        "",
        "| symbol | type | quality | rows | process | result | latency_ms | message |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in report["records"]:
        lines.append(
            "| {symbol} | {instrument_type} | {data_quality} | {row_count} | {process_row_count} | "
            "{result_row_count} | {latency_ms} | {message} |".format(**item)
        )
    if not report["records"]:
        lines.append("| - | - | - | 0 | 0 | 0 | 0 | 未执行 provider 调用 |")
    return "\n".join(lines) + "\n"
