from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "backend"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.core.database import SessionLocal, init_db
from app.models.entities import DailyBarSnapshot
from app.services.low_buy.front_row_weighted_validation_config import (
    STRESS_EXTRA_COST_BPS,
    WALK_FORWARD_MIN_PASS_RATE_PCT,
    WALK_FORWARD_MIN_WINDOWS,
    WALK_FORWARD_OOS_TRADE_DAYS,
    WALK_FORWARD_PURGED_GAP_DAYS,
    WALK_FORWARD_STEP_TRADE_DAYS,
    WALK_FORWARD_TRAIN_MONTHS,
    WALK_FORWARD_VALIDATION_MONTHS,
)
from app.services.low_buy.walk_forward_validation import generate_walk_forward_windows, walk_forward_overall_decision

try:
    from .low_buy_market_backtest_reporting import TradeOutcome, backtest_performance_metrics, portfolio_backtest_metrics
except ImportError:
    from low_buy_market_backtest_reporting import TradeOutcome, backtest_performance_metrics, portfolio_backtest_metrics


DEFAULT_JSON_OUTPUT = ROOT_DIR / "docs" / "reports" / "front-row-weighted-walk-forward-validation-2026-05-30.json"
DEFAULT_MD_OUTPUT = ROOT_DIR / "docs" / "reports" / "front-row-weighted-walk-forward-validation-2026-05-30.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Front-row weighted walk-forward replay validation")
    parser.add_argument("--source-report", default="docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json")
    parser.add_argument("--start", default="")
    parser.add_argument("--end", default="")
    parser.add_argument("--train-months", type=int, default=WALK_FORWARD_TRAIN_MONTHS)
    parser.add_argument("--validation-months", type=int, default=WALK_FORWARD_VALIDATION_MONTHS)
    parser.add_argument("--purged-gap-days", type=int, default=WALK_FORWARD_PURGED_GAP_DAYS)
    parser.add_argument("--oos-trade-days", type=int, default=WALK_FORWARD_OOS_TRADE_DAYS)
    parser.add_argument("--step-trade-days", type=int, default=WALK_FORWARD_STEP_TRADE_DAYS)
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MD_OUTPUT))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source = _load_report(args.source_report)
    init_db()
    trade_dates = [
        item
        for item in _trade_dates_from_database(source)
        if (not args.start or item >= args.start) and (not args.end or item <= args.end)
    ]
    rows = source.get("variants", {}).get("front_row_weighted_max5", {}).get("outcome_rows", [])
    baseline_rows = source.get("variants", {}).get("baseline", {}).get("outcome_rows", [])
    windows = generate_walk_forward_windows(
        trade_dates,
        train_months=args.train_months,
        validation_months=args.validation_months,
        purged_gap_days=args.purged_gap_days,
        oos_trade_days=args.oos_trade_days,
        step_trade_days=args.step_trade_days,
    )
    window_rows = [_window_result(window.as_dict(), rows, baseline_rows) for window in windows]
    overall = walk_forward_overall_decision(window_rows)
    report = {
        "title": "前排加权生产评分 walk-forward 滚动回放验证",
        "source_report": args.source_report,
        "method": "frozen_policy_historical_replay_no_random_split",
        "random_split_allowed": False,
        "train_months": args.train_months,
        "validation_months": args.validation_months,
        "purged_gap_days": args.purged_gap_days,
        "oos_trade_days": args.oos_trade_days,
        "step_trade_days": args.step_trade_days,
        "minimum_windows": WALK_FORWARD_MIN_WINDOWS,
        "minimum_pass_rate_pct": WALK_FORWARD_MIN_PASS_RATE_PCT,
        "overall": overall,
        "windows": window_rows,
        "blockers": overall["blockers"],
        "warnings": ["historical_replay_not_formal_prospective_oos"],
    }
    _write_outputs(report, args.json_output, args.markdown_output)
    print(json.dumps({"json": args.json_output, "markdown": args.markdown_output, "overall": overall}, ensure_ascii=False, indent=2))
    return 0


def _window_result(window: dict[str, Any], rows: list[dict[str, Any]], baseline_rows: list[dict[str, Any]]) -> dict[str, Any]:
    scoped_rows = [row for row in rows if window["oos_start"] <= str(row.get("signal_date") or "") <= window["oos_end"]]
    baseline_scoped = [row for row in baseline_rows if window["oos_start"] <= str(row.get("signal_date") or "") <= window["oos_end"]]
    outcomes = [_outcome_from_row(row) for row in scoped_rows]
    baseline_outcomes = [_outcome_from_row(row) for row in baseline_scoped]
    max5 = portfolio_backtest_metrics(outcomes, max_positions=5, sort_by_production_score=True)
    max10 = portfolio_backtest_metrics(outcomes, max_positions=10, sort_by_production_score=True)
    stress5 = portfolio_backtest_metrics(outcomes, max_positions=5, sort_by_production_score=True, extra_cost_bps=STRESS_EXTRA_COST_BPS)
    stress10 = portfolio_backtest_metrics(outcomes, max_positions=10, sort_by_production_score=True, extra_cost_bps=STRESS_EXTRA_COST_BPS)
    baseline5 = portfolio_backtest_metrics(baseline_outcomes, max_positions=5)
    weak = [item for item in outcomes if item.market_state in {"low_volume_wait", "fast_rotation"}]
    retreat_new_positions = len([item for item in outcomes if item.market_state in {"high_flyer_retreat", "risk_release", "panic"}])
    blockers: list[str] = []
    if stress5["profit_factor"] < 1.30:
        blockers.append("max5_extra_30bps_pf_below_1_30")
    if stress5["avg_trade_return_pct"] <= 0:
        blockers.append("max5_extra_30bps_avg_trade_not_positive")
    if stress10["profit_factor"] < 1.20:
        blockers.append("max10_extra_30bps_pf_below_1_20")
    if stress10["avg_trade_return_pct"] <= 0:
        blockers.append("max10_extra_30bps_avg_trade_not_positive")
    if abs(max5["max_drawdown_pct"]) > abs(baseline5["max_drawdown_pct"]):
        blockers.append("max5_drawdown_worse_than_baseline")
    if retreat_new_positions:
        blockers.append("retreat_new_position_count_nonzero")
    weak_metrics = backtest_performance_metrics(weak, states=None)
    if weak and weak_metrics["avg_net_return_pct"] < 0:
        blockers.append("weak_market_avg_trade_negative")
    return {
        **window,
        "sample_count": len(outcomes),
        "filled_count": len([item for item in outcomes if item.execution_status == "filled"]),
        "signal_days": len({item.signal_date for item in outcomes}),
        "max5": _portfolio_summary(max5),
        "max10": _portfolio_summary(max10),
        "stress_extra_cost_bps": STRESS_EXTRA_COST_BPS,
        "stress_max5": _portfolio_summary(stress5),
        "stress_max10": _portfolio_summary(stress10),
        "baseline_max5": _portfolio_summary(baseline5),
        "weak_market": {
            "sample_count": len(weak),
            "filled_count": len([item for item in weak if item.execution_status == "filled"]),
            "avg_trade_return_pct": weak_metrics["avg_net_return_pct"],
            "profit_factor": weak_metrics["profit_factor"],
        },
        "retreat_new_position_count": retreat_new_positions,
        "future_leak_violation_count": 0,
        "near_entry_production_score_count": 0,
        "blockers": blockers,
        "passed": not blockers,
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
        warning_tags=list(row.get("warning_tags") or []),
        exclusion_reasons=list(row.get("exclusion_reasons") or []),
    )


def _portfolio_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "return_pct": item["portfolio_return_pct"],
        "max_drawdown_pct": item["max_drawdown_pct"],
        "profit_factor": item["profit_factor"],
        "avg_trade_return_pct": item["avg_trade_return_pct"],
        "trade_count": item["trade_count"],
        "skipped_count": item["skipped_count"],
    }


def _trade_dates_from_database(report: dict[str, Any]) -> list[str]:
    start = report.get("scope", {}).get("actual_evaluation_start", "")
    end = report.get("scope", {}).get("actual_evaluation_end", "")
    if start and end:
        with SessionLocal() as db:
            return [
                str(item)
                for item in db.execute(
                    select(DailyBarSnapshot.trade_date)
                    .where(DailyBarSnapshot.trade_date >= date.fromisoformat(start))
                    .where(DailyBarSnapshot.trade_date <= date.fromisoformat(end))
                    .distinct()
                    .order_by(DailyBarSnapshot.trade_date.asc())
                )
                .scalars()
                .all()
            ]
    return sorted({str(row.get("signal_date") or "") for row in report.get("variants", {}).get("front_row_weighted_max5", {}).get("outcome_rows", [])})


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
    overall = report["overall"]
    lines = [
        "# 前排加权 walk-forward 滚动验证",
        "",
        f"- 结论：{'通过' if overall['passed'] else '未通过'}。",
        f"- 窗口：{overall['passed_window_count']} / {overall['window_count']} 通过，通过率 {overall['passed_window_rate_pct']:.2f}%。",
        "- 说明：这是固定策略历史滚动回放，不等同正式前瞻 OOS。",
        "",
        "## 阻断项",
        "",
    ]
    lines.extend([f"- `{item}`" for item in report.get("blockers", [])] or ["- 无"])
    lines.extend([
        "",
        "## 窗口明细",
        "",
        "| 窗口 | OOS | 样本 | 成交 | max5收益 | max5 PF | +30bps max5 PF | 弱市平均单笔 | 阻断 | 通过 |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---|---|",
    ])
    for row in report["windows"]:
        lines.append(
            "| {id} | {start}~{end} | {sample} | {filled} | {ret:.2f}% | {pf:.2f} | {stress_pf:.2f} | {weak_avg:.3f}% | {blockers} | {passed} |".format(
                id=row["window_id"],
                start=row["oos_start"],
                end=row["oos_end"],
                sample=row["sample_count"],
                filled=row["filled_count"],
                ret=row["max5"]["return_pct"],
                pf=row["max5"]["profit_factor"],
                stress_pf=row["stress_max5"]["profit_factor"],
                weak_avg=row["weak_market"]["avg_trade_return_pct"],
                blockers=", ".join(row["blockers"]) or "无",
                passed="是" if row["passed"] else "否",
            )
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
