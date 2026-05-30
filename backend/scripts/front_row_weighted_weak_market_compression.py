from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "backend"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.services.low_buy.front_row_weighted_validation_config import WEAK_MARKET_POLICIES
from app.services.low_buy.weak_market_candidate_gate import filter_rows_for_weak_market_policy

try:
    from .low_buy_market_backtest_reporting import TradeOutcome, backtest_performance_metrics, portfolio_backtest_metrics
except ImportError:
    from low_buy_market_backtest_reporting import TradeOutcome, backtest_performance_metrics, portfolio_backtest_metrics


DEFAULT_JSON_OUTPUT = ROOT_DIR / "docs" / "reports" / "front-row-weighted-weak-market-compression-2026-05-30.json"
DEFAULT_MD_OUTPUT = ROOT_DIR / "docs" / "reports" / "front-row-weighted-weak-market-compression-2026-05-30.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Front-row weighted weak-market compression A/B")
    parser.add_argument("--source-report", default="docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json")
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MD_OUTPUT))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = _load_report(args.source_report)
    rows = report.get("variants", {}).get("front_row_weighted_max5", {}).get("outcome_rows", [])
    results = {name: _policy_result(name, rows) for name in WEAK_MARKET_POLICIES}
    recommended = results.get("weak_soft_score86_cap20", {})
    blockers: list[str] = []
    if float(recommended.get("weak_market", {}).get("avg_trade_return_pct") or 0.0) < 0:
        blockers.append("weak_market_avg_trade_negative")
    if int(recommended.get("weak_market", {}).get("filled_count") or 0) < 20:
        blockers.append("weak_market_sample_insufficient_keep_watch_only")
    output = {
        "title": "前排加权弱市候选压缩 A/B",
        "source_report": args.source_report,
        "production_sort_replaced": False,
        "weak_market_policy_applied_to": "shadow_paper_backtest_only",
        "recommended_policy": "weak_soft_score86_cap20",
        "results": results,
        "decision": {
            "passed": not blockers,
            "blockers": blockers,
            "status": "weak_market_passed" if not blockers else "weak_market_blocked",
        },
    }
    _write_outputs(output, args.json_output, args.markdown_output)
    print(json.dumps({"json": args.json_output, "markdown": args.markdown_output, "decision": output["decision"]}, ensure_ascii=False, indent=2))
    return 0


def _policy_result(policy_name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    kept_rows, demotion_reasons = filter_rows_for_weak_market_policy(rows, policy_name=policy_name)
    outcomes = [_outcome_from_row(row) for row in kept_rows]
    weak_outcomes = [item for item in outcomes if item.market_state in {"low_volume_wait", "fast_rotation"}]
    metrics = backtest_performance_metrics(outcomes, states=None)
    weak_metrics = backtest_performance_metrics(weak_outcomes, states=None)
    policy = WEAK_MARKET_POLICIES[policy_name]
    return {
        "policy": {
            "name": policy.name,
            "allow_weak_market": policy.allow_weak_market,
            "soft_buy_only": policy.soft_buy_only,
            "min_production_score": policy.min_production_score,
            "weak_market_position_cap_pct": policy.weak_market_position_cap_pct,
        },
        "sample_count": len(outcomes),
        "filled_count": len([item for item in outcomes if item.execution_status == "filled"]),
        "signal_days": metrics["signal_days"],
        "portfolio_max5": _portfolio_summary(
            portfolio_backtest_metrics(
                outcomes,
                max_positions=5,
                sort_by_production_score=True,
                weak_market_position_cap_pct=policy.weak_market_position_cap_pct,
            )
        ),
        "portfolio_max10": _portfolio_summary(
            portfolio_backtest_metrics(
                outcomes,
                max_positions=10,
                sort_by_production_score=True,
                weak_market_position_cap_pct=policy.weak_market_position_cap_pct,
            )
        ),
        "weak_market": {
            "sample_count": len(weak_outcomes),
            "filled_count": len([item for item in weak_outcomes if item.execution_status == "filled"]),
            "signal_days": weak_metrics["signal_days"],
            "avg_trade_return_pct": weak_metrics["avg_net_return_pct"],
            "profit_factor": weak_metrics["profit_factor"],
        },
        "demotion_reasons": demotion_reasons,
    }


def _outcome_from_row(row: dict[str, Any]) -> TradeOutcome:
    return TradeOutcome(
        symbol=str(row.get("symbol") or ""),
        name=str(row.get("name") or ""),
        signal_date=str(row.get("signal_date") or ""),
        strategy_key=str(row.get("strategy_key") or ""),
        buy_signal_state=str(row.get("buy_signal_state") or "buy_now"),
        entry_price=float(row.get("entry_price") or 0.0),
        execution_status=str(row.get("execution_status") or "not_filled"),
        net_return_pct=float(row.get("net_return_pct") or 0.0),
        execution_exit_reason=str(row.get("execution_exit_reason") or ""),
        return_1d=0.0,
        return_2d=0.0,
        return_3d=0.0,
        return_4d=0.0,
        return_5d=0.0,
        max_gain_5d=0.0,
        max_drawdown_5d=0.0,
        entry_zone_low=float(row.get("entry_zone_low") or 0.0),
        entry_zone_high=float(row.get("entry_zone_high") or 0.0),
        entry_trade_date=str(row.get("entry_trade_date") or ""),
        exit_trade_date=str(row.get("exit_trade_date") or ""),
        market_state=str(row.get("market_state") or ""),
        sector_name=str(row.get("sector_name") or ""),
        production_score=row.get("production_score"),
        watch_score=row.get("watch_score"),
        production_decision=str(row.get("production_decision") or ""),
        front_row_tier=str(row.get("front_row_tier") or "unknown"),
    )


def _portfolio_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "return_pct": item["portfolio_return_pct"],
        "max_drawdown_pct": item["max_drawdown_pct"],
        "profit_factor": item["profit_factor"],
        "avg_trade_return_pct": item["avg_trade_return_pct"],
        "trade_count": item["trade_count"],
        "skipped_count": item["skipped_count"],
        "skip_reason_counts": item.get("skip_reason_counts", {}),
    }


def _load_report(path: str) -> dict[str, Any]:
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
    lines = [
        "# 前排加权弱市候选压缩 A/B",
        "",
        f"- 结论：{'通过' if decision['passed'] else '未通过'}。",
        "- 本报告只用于 Shadow/Paper，不替换生产排序。",
        f"- 推荐策略：`{report['recommended_policy']}`。",
        "",
        "## 阻断项",
        "",
    ]
    lines.extend([f"- `{item}`" for item in decision["blockers"]] or ["- 无"])
    lines.extend([
        "",
        "## 对比",
        "",
        "| 策略 | 样本 | 成交 | 信号日 | max5收益 | max5 PF | 弱市成交 | 弱市平均单笔 | 弱市 PF | 降级原因 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ])
    for key, item in report["results"].items():
        weak = item["weak_market"]
        lines.append(
            "| {key} | {sample} | {filled} | {signal_days} | {ret:.2f}% | {pf:.2f} | {weak_filled} | {weak_avg:.3f}% | {weak_pf:.2f} | {reasons} |".format(
                key=key,
                sample=item["sample_count"],
                filled=item["filled_count"],
                signal_days=item["signal_days"],
                ret=item["portfolio_max5"]["return_pct"],
                pf=item["portfolio_max5"]["profit_factor"],
                weak_filled=weak["filled_count"],
                weak_avg=weak["avg_trade_return_pct"],
                weak_pf=weak["profit_factor"],
                reasons=", ".join(f"{reason}:{count}" for reason, count in item["demotion_reasons"].items()) or "无",
            )
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
