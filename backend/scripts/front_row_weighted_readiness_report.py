from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_JSON_OUTPUT = ROOT_DIR / "docs" / "reports" / "front-row-weighted-production-readiness-2026-05-30.json"
DEFAULT_MD_OUTPUT = ROOT_DIR / "docs" / "reports" / "front-row-weighted-production-readiness-2026-05-30.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Front-row weighted combined production readiness report")
    parser.add_argument("--base-report", default="docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json")
    parser.add_argument("--freeze-manifest", default="docs/reports/front-row-weighted-validation-freeze-2026-05-30.json")
    parser.add_argument("--walk-forward-report", default="docs/reports/front-row-weighted-walk-forward-validation-2026-05-30.json")
    parser.add_argument("--tradability-report", default="docs/reports/front-row-weighted-minute-tick-tradability-2026-05-30.json")
    parser.add_argument("--weak-market-report", default="docs/reports/front-row-weighted-weak-market-compression-2026-05-30.json")
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MD_OUTPUT))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    base = _load(args.base_report)
    freeze = _load(args.freeze_manifest)
    walk_forward = _load(args.walk_forward_report)
    tradability = _load(args.tradability_report)
    weak_market = _load(args.weak_market_report)
    report = build_readiness_report(
        base=base,
        freeze=freeze,
        walk_forward=walk_forward,
        tradability=tradability,
        weak_market=weak_market,
        paths={
            "base_report": args.base_report,
            "freeze_manifest": args.freeze_manifest,
            "walk_forward_report": args.walk_forward_report,
            "tradability_report": args.tradability_report,
            "weak_market_report": args.weak_market_report,
        },
    )
    _write_outputs(report, args.json_output, args.markdown_output)
    print(json.dumps({"json": args.json_output, "markdown": args.markdown_output, "decision": report["decision"]}, ensure_ascii=False, indent=2))
    return 0


def build_readiness_report(
    *,
    base: dict[str, Any],
    freeze: dict[str, Any],
    walk_forward: dict[str, Any],
    tradability: dict[str, Any],
    weak_market: dict[str, Any],
    paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    blockers.extend(_list(base.get("decision", {}).get("blockers")))
    blockers.extend(_list(freeze.get("blockers")))
    blockers.extend(_list(walk_forward.get("blockers")))
    blockers.extend(_list(tradability.get("blockers")))
    blockers.extend(_list(weak_market.get("decision", {}).get("blockers")))
    warnings.extend(_list(base.get("decision", {}).get("warnings")))
    warnings.extend(_list(freeze.get("warnings")))
    warnings.extend(_list(walk_forward.get("warnings")))
    warnings.extend(_list(tradability.get("warnings")))
    if bool(base.get("summary", {}).get("production_sort_replaced")):
        blockers.append("production_sort_replaced_without_approval")
    if int(base.get("summary", {}).get("near_entry_production_score_count") or 0) != 0:
        blockers.append("near_entry_misclassified_into_production")
    if base.get("anti_future_function_audit", {}).get("future_leak_check") != "passed":
        blockers.append("future_leak_violation")
    blockers = sorted(set(blockers))
    warnings = sorted(set(warnings))
    status = _status(blockers)
    return {
        "title": "前排加权生产评分综合 readiness 报告",
        "paths": paths or {},
        "production_sort_replaced": bool(base.get("summary", {}).get("production_sort_replaced")),
        "deployed": False,
        "base_decision": base.get("decision", {}),
        "formal_oos": {
            "status": freeze.get("status"),
            "formal_oos_start": freeze.get("formal_oos_start"),
            "formal_oos_end": freeze.get("formal_oos_end"),
            "oos_window_trade_days": freeze.get("oos_window_trade_days"),
            "oos_signal_days": freeze.get("oos_signal_days"),
            "oos_sample_count": freeze.get("oos_sample_count"),
            "oos_filled_count": freeze.get("oos_filled_count"),
            "minimum_oos_trade_days": freeze.get("minimum_oos_trade_days"),
            "minimum_oos_filled_count": freeze.get("minimum_oos_filled_count"),
        },
        "walk_forward": walk_forward.get("overall", {}),
        "tradability": {
            "status": tradability.get("status"),
            "minute_coverage_pct": tradability.get("minute_coverage", {}).get("coverage_pct"),
            "tick_rows": tradability.get("tick_coverage", {}).get("tick_rows"),
            "fill_retention_pct": tradability.get("fill_retention_pct"),
        },
        "weak_market": weak_market.get("decision", {}),
        "decision": {
            "status": status,
            "recommend_small_traffic_observation": False,
            "blockers": blockers,
            "warnings": warnings,
            "next_action": "continue_shadow_paper_validation" if blockers else "small_traffic_candidate_pending_approval",
        },
    }


def _status(blockers: list[str]) -> str:
    if not blockers:
        return "small_traffic_candidate_pending_approval"
    if "oos_window_below_60_trade_days" in blockers:
        return "shadow_paper_extend_oos"
    if any(item.startswith("walk_forward") for item in blockers):
        return "shadow_paper_walk_forward_blocked"
    if any(item.startswith("minute_") or item.startswith("tick_") or item.startswith("tradability") for item in blockers):
        return "shadow_paper_tradability_blocked"
    if any(item.startswith("weak_market") for item in blockers):
        return "shadow_paper_weak_market_blocked"
    return "shadow_paper_not_ready"


def _list(value: Any) -> list[str]:
    return [str(item) for item in (value or []) if str(item or "").strip()]


def _load(path: str) -> dict[str, Any]:
    report_path = Path(path)
    if not report_path.is_absolute():
        report_path = ROOT_DIR / report_path
    return json.loads(report_path.read_text(encoding="utf-8"))


def _write_outputs(report: dict[str, Any], json_output: str, markdown_output: str) -> None:
    json_path = Path(json_output)
    md_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")


def render_markdown(report: dict[str, Any]) -> str:
    decision = report["decision"]
    oos = report["formal_oos"]
    walk = report["walk_forward"]
    trade = report["tradability"]
    lines = [
        "# 前排加权生产评分综合 readiness 报告",
        "",
        f"- 结论：`{decision['status']}`。",
        f"- 建议小流量生产观察：{'是' if decision['recommend_small_traffic_observation'] else '否'}。",
        f"- 下一步：`{decision['next_action']}`。",
        "- 未部署，未替换生产排序。",
        "",
        "## 阻断项",
        "",
    ]
    lines.extend([f"- `{item}`" for item in decision["blockers"]] or ["- 无"])
    lines.extend([
        "",
        "## OOS",
        "",
        f"- 状态：`{oos.get('status')}`。",
        f"- 正式 OOS 起止：{oos.get('formal_oos_start') or '-'} 至 {oos.get('formal_oos_end') or '-'}。",
        f"- OOS 交易日：{oos.get('oos_window_trade_days')} / {oos.get('minimum_oos_trade_days')}。",
        f"- OOS 信号日：{oos.get('oos_signal_days')}。",
        f"- OOS 成交样本：{oos.get('oos_filled_count')} / {oos.get('minimum_oos_filled_count')}。",
        "",
        "## Walk-forward",
        "",
        f"- 通过窗口：{walk.get('passed_window_count', 0)} / {walk.get('window_count', 0)}。",
        f"- 通过率：{walk.get('passed_window_rate_pct', 0.0):.2f}%。",
        "",
        "## 可成交性",
        "",
        f"- 状态：`{trade.get('status')}`。",
        f"- 分钟覆盖：{float(trade.get('minute_coverage_pct') or 0.0):.2f}%。",
        f"- tick 行数：{trade.get('tick_rows') or 0}。",
        f"- 可成交留存：{float(trade.get('fill_retention_pct') or 0.0):.2f}%。",
        "",
        "## 弱市压缩",
        "",
        f"- 状态：`{report.get('weak_market', {}).get('status')}`。",
    ])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
