#!/usr/bin/env python3
"""Summarize focused parameter walk-forward matrices for P1 strategies."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DATE = "2026-05-28"
BASE_VARIANT = "default_exit"
CANDIDATE_VARIANT = "quick_tp3_trailing1"
STRATEGY_SCOPES = ("first_board", "volume_shrink")
FIRST_TAKE_PROFIT_REASON = "触发首次止盈位。"


def build_summary(report_date: str = REPORT_DATE, root: Path = ROOT) -> dict[str, Any]:
    base = root / "docs" / "reports" / f"focus-strategy-parameter-walk-forward-{report_date}"
    combined = _scope_summary(
        scope_key="combined_first_board_volume_shrink",
        source_dir=base / "matrix-windows",
        root=root,
    )
    strategies = [
        _scope_summary(
            scope_key=strategy,
            source_dir=base / "strategy-matrix-windows" / strategy,
            root=root,
        )
        for strategy in STRATEGY_SCOPES
    ]
    strategy_pass_counts = {
        item["scope_key"]: item["passed_window_count"]
        for item in strategies
    }
    combined_masks_instability = any(
        item["passed_window_count"] < item["window_count"]
        for item in strategies
    )
    return {
        "title": "P1 核心策略参数窄网格 walk-forward 实算摘要",
        "report_date": report_date,
        "scope": {
            "candidate_variant": CANDIDATE_VARIANT,
            "baseline_variant": BASE_VARIANT,
            "strategy_keys": list(STRATEGY_SCOPES),
            "combined_window_count": combined["window_count"],
            "per_strategy_window_count": sum(item["window_count"] for item in strategies),
            "total_matrix_window_count": combined["window_count"]
            + sum(item["window_count"] for item in strategies),
        },
        "rules": {
            "no_production_param_write": True,
            "materialization_mode": "isolated",
            "random_split_allowed": False,
            "pass_vs_default": (
                "candidate PF > default PF, total return >= default, and max drawdown is not worse."
            ),
            "production": (
                "This P1 narrow grid is Shadow/research evidence only. Production still requires "
                "purged-gap candidate grids and settled online Shadow samples."
            ),
        },
        "combined": combined,
        "strategies": strategies,
        "aggregate_findings": {
            "combined_passed_all_windows": combined["passed_window_count"] == combined["window_count"],
            "strategy_pass_counts": strategy_pass_counts,
            "combined_result_masks_strategy_instability": combined_masks_instability,
            "profit_mechanism": _profit_mechanism([combined, *strategies]),
            "production_eligible": False,
            "shadow_candidate": False,
            "strategy_specific_shadow_candidates": [
                item["scope_key"]
                for item in strategies
                if item["shadow_candidate"] and item["passed_window_count"] == item["window_count"]
            ],
            "research_only_or_retest": [
                item["scope_key"]
                for item in strategies
                if item["passed_window_count"] < item["window_count"]
            ],
        },
        "promotion_blockers": _promotion_blockers(combined, strategies),
        "remaining_work": [
            "剩余四个重点策略需先让信号闸门产生足够 confirmed 成交样本，再进入参数矩阵。",
            "任何生产参数变更前，必须补 purged-gap 参数稳定性检查。",
            "启用执行默认值前，必须积累线上已结算 Shadow 样本。",
        ],
    }


def write_summary(payload: dict[str, Any], root: Path = ROOT) -> tuple[Path, Path]:
    base = root / "docs" / "reports" / f"focus-strategy-parameter-walk-forward-{payload['report_date']}"
    json_path = base / "summary.json"
    md_path = base / "summary.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return md_path, json_path


def render_markdown(payload: dict[str, Any]) -> str:
    findings = payload["aggregate_findings"]
    lines = [
        f"# {payload['title']}",
        "",
        f"- 报告日期：{payload['report_date']}",
        f"- 候选参数：`{payload['scope']['candidate_variant']}` vs `{payload['scope']['baseline_variant']}`",
        f"- 矩阵窗口：{payload['scope']['total_matrix_window_count']} 个",
        f"- 生产可用：{'是' if findings['production_eligible'] else '否'}",
        f"- Shadow 候选：{'是' if findings['shadow_candidate'] else '否'}",
        f"- 收益机制：{findings['profit_mechanism']}",
        f"- 阻断：{', '.join(payload['promotion_blockers'])}",
        "",
        "| 范围 | 窗口 | 通过 | 平均 PF 改善 | 平均收益改善 | 平均回撤改善 | 候选首次止盈占比 | 首次止盈占比提升 | Shadow |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in [payload["combined"], *payload["strategies"]]:
        lines.append(
            "| {key} | {windows} | {passed} | {dpf} | {dret}% | {dmdd} | {tp}% | {dtp}% | {shadow} |".format(
                key=row["scope_key"],
                windows=row["window_count"],
                passed=row["passed_window_count"],
                dpf=row["aggregate_delta"]["avg_delta_profit_factor"],
                dret=row["aggregate_delta"]["avg_delta_total_return_pct"],
                dmdd=row["aggregate_delta"]["avg_delta_max_drawdown_pct"],
                tp=row["aggregate_delta"]["avg_candidate_first_take_profit_exit_pct"],
                dtp=row["aggregate_delta"]["avg_delta_first_take_profit_exit_pct"],
                shadow="是" if row["shadow_candidate"] else "否",
            )
        )
    lines.extend([
        "",
        "## 窗口明细",
        "",
        "| 范围 | 窗口 | OOS | 基线 PF | 候选 PF | PF 改善 | 基线收益 | 候选收益 | 收益改善 | 基线回撤 | 候选回撤 | 回撤改善 | 通过 |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ])
    for scope in [payload["combined"], *payload["strategies"]]:
        for window in scope["windows"]:
            base = window[BASE_VARIANT]
            candidate = window[CANDIDATE_VARIANT]
            lines.append(
                "| {scope} | {idx} | {start}~{end} | {bpf} | {qpf} | {dpf} | {bret}% | {qret}% | {dret}% | {bdd}% | {qdd}% | {ddd} | {ok} |".format(
                    scope=scope["scope_key"],
                    idx=window["window_id"],
                    start=window["oos_start"],
                    end=window["oos_end"],
                    bpf=base["profit_factor"],
                    qpf=candidate["profit_factor"],
                    dpf=candidate["delta_profit_factor"],
                    bret=base["total_return_pct"],
                    qret=candidate["total_return_pct"],
                    dret=candidate["delta_total_return_pct"],
                    bdd=base["max_drawdown_pct"],
                    qdd=candidate["max_drawdown_pct"],
                    ddd=candidate["delta_max_drawdown_pct"],
                    ok="是" if candidate["pass_vs_default"] else "否",
                )
            )
    lines.extend(["", "## 剩余工作", ""])
    for item in payload["remaining_work"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _scope_summary(*, scope_key: str, source_dir: Path, root: Path) -> dict[str, Any]:
    windows = [_window_row(index + 1, path, root=root) for index, path in enumerate(sorted(source_dir.glob("*.json")))]
    passed = [item for item in windows if item[CANDIDATE_VARIANT]["pass_vs_default"]]
    return {
        "scope_key": scope_key,
        "source_dir": str(source_dir.relative_to(root)),
        "window_count": len(windows),
        "passed_window_count": len(passed),
        "pass_rate_pct": _round(len(passed) / max(len(windows), 1) * 100),
        "shadow_candidate": len(windows) > 0 and len(passed) == len(windows),
        "production_eligible": False,
        "windows": windows,
        "aggregate_delta": _aggregate_delta(windows),
    }


def _window_row(window_id: int, path: Path, *, root: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = {row["variant_key"]: row for row in payload.get("rows", [])}
    baseline = _variant_row(rows[BASE_VARIANT])
    candidate = _variant_row(rows[CANDIDATE_VARIANT], baseline)
    scope = payload.get("scope") or {}
    return {
        "window_id": window_id,
        "source_path": str(path.relative_to(root)),
        "oos_start": rows[BASE_VARIANT].get("evaluation_start") or scope.get("start"),
        "oos_end": rows[BASE_VARIANT].get("evaluation_end") or scope.get("end"),
        BASE_VARIANT: baseline,
        CANDIDATE_VARIANT: candidate,
    }


def _variant_row(row: dict[str, Any], baseline: dict[str, Any] | None = None) -> dict[str, Any]:
    trade_count = int(row.get("filled_count") or 0)
    result = {
        "profit_factor": _round(row.get("profit_factor")),
        "max_drawdown_pct": _round(row.get("max_drawdown_pct")),
        "total_return_pct": _round(row.get("total_return_pct")),
        "win_rate_pct": _round(row.get("net_win_rate")),
        "avg_trade_return_pct": _round(row.get("avg_net_return_pct")),
        "stop_loss_rate_pct": _round(row.get("stop_loss_rate")),
        "trade_count": trade_count,
        "first_take_profit_exit_count": int((row.get("filled_exit_reason_counts") or {}).get(FIRST_TAKE_PROFIT_REASON) or 0),
    }
    result["first_take_profit_exit_pct"] = _round(
        result["first_take_profit_exit_count"] / max(trade_count, 1) * 100
    )
    if baseline:
        result["delta_profit_factor"] = _round(result["profit_factor"] - baseline["profit_factor"])
        result["delta_max_drawdown_pct"] = _round(result["max_drawdown_pct"] - baseline["max_drawdown_pct"])
        result["delta_total_return_pct"] = _round(result["total_return_pct"] - baseline["total_return_pct"])
        result["delta_first_take_profit_exit_pct"] = _round(
            result["first_take_profit_exit_pct"] - baseline["first_take_profit_exit_pct"]
        )
        result["pass_vs_default"] = (
            result["delta_profit_factor"] > 0
            and result["delta_total_return_pct"] >= 0
            and result["delta_max_drawdown_pct"] >= 0
        )
    return result


def _aggregate_delta(windows: list[dict[str, Any]]) -> dict[str, Any]:
    if not windows:
        return {
            "avg_delta_profit_factor": 0.0,
            "avg_delta_total_return_pct": 0.0,
            "avg_delta_max_drawdown_pct": 0.0,
            "avg_candidate_first_take_profit_exit_pct": 0.0,
            "avg_delta_first_take_profit_exit_pct": 0.0,
        }
    candidate_rows = [window[CANDIDATE_VARIANT] for window in windows]
    return {
        "avg_delta_profit_factor": _avg(candidate_rows, "delta_profit_factor"),
        "avg_delta_total_return_pct": _avg(candidate_rows, "delta_total_return_pct"),
        "avg_delta_max_drawdown_pct": _avg(candidate_rows, "delta_max_drawdown_pct"),
        "avg_candidate_first_take_profit_exit_pct": _avg(candidate_rows, "first_take_profit_exit_pct"),
        "avg_delta_first_take_profit_exit_pct": _avg(candidate_rows, "delta_first_take_profit_exit_pct"),
    }


def _profit_mechanism(scopes: list[dict[str, Any]]) -> str:
    avg_take_profit = mean(
        scope["aggregate_delta"]["avg_candidate_first_take_profit_exit_pct"]
        for scope in scopes
        if scope["window_count"]
    )
    avg_delta_take_profit = mean(
        scope["aggregate_delta"]["avg_delta_first_take_profit_exit_pct"]
        for scope in scopes
        if scope["window_count"]
    )
    if avg_take_profit >= 35 and avg_delta_take_profit >= 20:
        return "主要来自 3% 首次止盈与 1% 移动防守提升的冲高兑现，而非放宽持仓收益。"
    return "未观察到首次止盈退出占比主导，仍需逐笔归因。"


def _promotion_blockers(combined: dict[str, Any], strategies: list[dict[str, Any]]) -> list[str]:
    blockers = [
        "production_param_write_from_backtest_forbidden",
        "purged_gap_candidate_grid_not_executed",
        "online_shadow_settled_sample_lt_required",
    ]
    if combined["window_count"] < 7 or any(item["window_count"] < 7 for item in strategies):
        blockers.append("focus_strategy_parameter_walk_forward_incomplete")
    if any(item["passed_window_count"] < item["window_count"] for item in strategies):
        blockers.append("strategy_specific_window_not_all_passed")
    return blockers


def _avg(rows: list[dict[str, Any]], key: str) -> float:
    return _round(sum(float(row.get(key) or 0.0) for row in rows) / len(rows))


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
