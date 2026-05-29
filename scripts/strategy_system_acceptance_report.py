#!/usr/bin/env python3
"""Build a read-only acceptance report for the strategy system goal."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SCRIPTS = ROOT / "scripts"
for path in (ROOT, BACKEND, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.core.config import AppSettings  # noqa: E402
from app.services.low_buy.old_duck_head import OLD_DUCK_HEAD_FACTOR, OLD_DUCK_HEAD_STRATEGIES  # noqa: E402
from app.services.low_buy.shared import LowBuyThresholds  # noqa: E402
from app.services.low_buy.strategy_families import LOW_BUY_STRATEGY_KEYS, unclassified_low_buy_strategies  # noqa: E402
from strategy_system_requirement_audit import (  # noqa: E402
    build_requirement_audit,
    build_test_coverage_matrix,
    render_requirement_audit_markdown,
    render_test_coverage_matrix_markdown,
)
from strategy_system_acceptance_walk_forward import walk_forward_evidence_check  # noqa: E402
from strategy_system_promotion_plan import build_promotion_action_plan, render_promotion_action_plan_markdown  # noqa: E402


SOURCE_DATE = "2026-05-28"


def build_report(*, report_date: str = SOURCE_DATE, root: Path = ROOT) -> dict[str, Any]:
    sources = _read_sources(root, report_date)
    settings = AppSettings(auth_secret_key="x" * 64, tquant_settings_encryption_key="y" * 64)
    checks = [
        _strategy_family_check(sources["backtest"]),
        _main_force_check(sources["closed_loop"], settings),
        _old_duck_head_check(),
        _exit_model_check(sources["closed_loop"]),
        _backtest_loop_check(sources["backtest"]),
        _anti_overfit_check(sources["backtest"], sources["optimization"]),
        _requirements_source_check(root),
        walk_forward_evidence_check(sources),
        _frontend_check(root),
        _safety_check(sources["optimization"], settings),
    ]
    blockers = _production_blockers(sources)
    complete_count = sum(1 for item in checks if item["complete"])
    report = {
        "title": "策略体系最小生产闭环验收报告",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "report_date": report_date,
        "source_files": _source_files(report_date),
        "overall_status": (
            "readonly_shadow_loop_complete_production_blocked"
            if complete_count == len(checks)
            else "incomplete"
        ),
        "minimal_readonly_loop_complete": complete_count == len(checks),
        "production_trade_ready": False,
        "completion_pct": round(complete_count / len(checks) * 100.0, 2),
        "checks": checks,
        "production_blockers": blockers,
        "final_status": {
            "strategy_classified": _check_complete(checks, "strategy_family_classification"),
            "main_force_side_channel_in_use": _check_complete(checks, "main_force_readonly_shadow"),
            "old_duck_head_factorized": _check_complete(checks, "old_duck_head_factorized"),
            "exit_model_connected_to_paper": _check_complete(checks, "paper_exit_model_readonly_shadow"),
            "original_ranking_or_trade_execution_affected": False,
            "reason": "策略体系已形成只读/Shadow 最小闭环；真实交易生产放行仍被数据、walk-forward、purged-gap 与 Shadow settled 样本门禁阻断。",
        },
    }
    report["requirement_audit"] = build_requirement_audit(report)
    report["test_coverage_matrix"] = build_test_coverage_matrix(root)
    report["promotion_action_plan"] = build_promotion_action_plan(blockers)
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 策略体系最小生产闭环验收报告",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 验收状态：{report['overall_status']}",
        f"- 最小只读/Shadow 闭环：{'完成' if report['minimal_readonly_loop_complete'] else '未完成'}",
        f"- 真实交易生产放行：{'是' if report['production_trade_ready'] else '否'}",
        f"- 完成度：{report['completion_pct']}%",
        "",
        "## 检查项",
        "",
        "| 检查 | 状态 | 结论 |",
        "|---|---|---|",
    ]
    for item in report["checks"]:
        lines.append(f"| {item['title']} | {item['status']} | {item['summary']} |")
    family_evidence = next(
        (item["evidence"]["family_evidence"] for item in report["checks"] if item["key"] == "walk_forward_evidence_snapshot"),
        {},
    )
    families = family_evidence.get("families") or []
    if families:
        lines.extend(
            [
                "",
                "## 策略族 walk-forward 证据映射",
                "",
                "| 策略族 | 策略 | 证据来源 | 生产放行 | 主要缺口 |",
                "|---|---|---|---|---|",
            ]
        )
        for row in families:
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row["family_text"]),
                        ", ".join(row["strategy_keys"]),
                        ", ".join(row["evidence_sources"]),
                        _yes_no(row["production_ready"]),
                        ", ".join(row["missing_for_production"][:3]),
                    ]
                )
                + " |"
            )
    lines.extend([""] + render_requirement_audit_markdown(report["requirement_audit"]))
    lines.extend([""] + render_test_coverage_matrix_markdown(report["test_coverage_matrix"]))
    lines.extend([""] + render_promotion_action_plan_markdown(report["promotion_action_plan"]))
    lines.extend(["", "## 生产阻断", ""])
    for blocker in report["production_blockers"]:
        lines.append(f"- {blocker['source']}：{blocker['key']}，{blocker['reason']}")
    final = report["final_status"]
    lines.extend(
        [
            "",
            "## 最终状态",
            "",
            f"- 策略是否已完成归类：{_yes_no(final['strategy_classified'])}",
            f"- 主力观测模型是否已投入旁路生产使用：{_yes_no(final['main_force_side_channel_in_use'])}",
            f"- 老鸭头是否仍保持因子化：{_yes_no(final['old_duck_head_factorized'])}",
            f"- 止盈止损辅助模型是否已接入模拟盘：{_yes_no(final['exit_model_connected_to_paper'])}",
            f"- 是否影响原有策略排序或交易执行：{_yes_no(final['original_ranking_or_trade_execution_affected'])}",
            f"- 说明：{final['reason']}",
        ]
    )
    return "\n".join(lines) + "\n"


def _strategy_family_check(backtest: dict[str, Any]) -> dict[str, Any]:
    summary = backtest.get("strategy_family_summary") or {}
    missing = unclassified_low_buy_strategies()
    complete = (
        not missing
        and summary.get("strategy_count") == len(LOW_BUY_STRATEGY_KEYS)
        and summary.get("family_count", 0) >= 12
        and summary.get("sorting_effect") == "none"
    )
    return _check(
        "strategy_family_classification",
        "策略族归类",
        complete,
        "17 个低吸策略已归入 13 个策略族，旧 items 接口保持兼容。",
        {
            "family_count": summary.get("family_count"),
            "strategy_count": summary.get("strategy_count"),
            "unclassified": missing,
            "sorting_effect": summary.get("sorting_effect"),
        },
    )


def _main_force_check(closed_loop: dict[str, Any], settings: AppSettings) -> dict[str, Any]:
    shadow = closed_loop.get("main_force_model_shadow") or {}
    complete = (
        settings.main_force_model_enabled
        and settings.main_force_model_shadow_enabled
        and settings.main_force_model_display_enabled
        and not settings.main_force_model_ranking_enabled
        and not settings.main_force_model_paper_suggestion_enabled
        and shadow.get("shadow_only") is True
        and shadow.get("production_effect") == "readonly_shadow"
        and shadow.get("promotion_ready") is False
    )
    return _check(
        "main_force_readonly_shadow",
        "主力观测模型旁路",
        complete,
        "主力模型已只读/Shadow 接入候选与模拟盘展示，默认不加排序权重、不出自动小仓建议。",
        {
            "record_count": shadow.get("record_count"),
            "settled_count": shadow.get("settled_count"),
            "promotion_ready": shadow.get("promotion_ready"),
            "promotion_blockers": shadow.get("promotion_blockers"),
            "ranking_enabled_default": settings.main_force_model_ranking_enabled,
            "paper_suggestion_enabled_default": settings.main_force_model_paper_suggestion_enabled,
        },
    )


def _old_duck_head_check() -> dict[str, Any]:
    weights = LowBuyThresholds().FACTOR_WEIGHTS
    complete = (
        OLD_DUCK_HEAD_FACTOR in weights
        and weights[OLD_DUCK_HEAD_FACTOR] > 0
        and "old_duck_head" not in LOW_BUY_STRATEGY_KEYS
        and bool(OLD_DUCK_HEAD_STRATEGIES)
    )
    return _check(
        "old_duck_head_factorized",
        "老鸭头结构因子",
        complete,
        "老鸭头保持结构因子，不新增独立策略入口，只给适用低吸/N 字策略加分。",
        {
            "factor": OLD_DUCK_HEAD_FACTOR,
            "weight": weights.get(OLD_DUCK_HEAD_FACTOR),
            "standalone_strategy_registered": "old_duck_head" in LOW_BUY_STRATEGY_KEYS,
            "applicable_strategy_count": len(OLD_DUCK_HEAD_STRATEGIES),
        },
    )


def _exit_model_check(closed_loop: dict[str, Any]) -> dict[str, Any]:
    shadow = closed_loop.get("auxiliary_model_shadow") or {}
    complete = (
        shadow.get("shadow_only") is True
        and shadow.get("hard_stop_override_allowed") is False
        and shadow.get("promotion_ready") is False
        and shadow.get("production_effect") == "none_shadow_only"
    )
    return _check(
        "paper_exit_model_readonly_shadow",
        "止盈止损辅助模型",
        complete,
        "退出模型已接入模拟盘 Shadow 记录与只读展示，不自动执行，不覆盖硬止损。",
        {
            "record_count": shadow.get("record_count"),
            "settled_count": shadow.get("settled_count"),
            "promotion_ready": shadow.get("promotion_ready"),
            "hard_stop_override_allowed": shadow.get("hard_stop_override_allowed"),
            "promotion_blockers": shadow.get("promotion_blockers"),
        },
    )


def _backtest_loop_check(backtest: dict[str, Any]) -> dict[str, Any]:
    summary = backtest.get("strategy_family_summary") or {}
    required = {"win_rate_pct", "total_return_pct", "max_drawdown_pct", "profit_factor", "parameter_change_count"}
    families = summary.get("families") or []
    metrics_present = bool(families) and all(required.issubset(item.keys()) for item in families)
    complete = (
        summary.get("status") == "research_only"
        and summary.get("production_parameter_change_allowed") is False
        and summary.get("sorting_effect") == "none"
        and metrics_present
    )
    return _check(
        "strategy_family_backtest_loop",
        "策略族回测与调参闭环",
        complete,
        "策略族维度已输出参数建议、胜率、收益率、最大回撤和盈亏比，但只作为研究报告。",
        {
            "family_count": summary.get("family_count"),
            "strategy_count": summary.get("strategy_count"),
            "metrics_present": metrics_present,
            "production_parameter_change_allowed": summary.get("production_parameter_change_allowed"),
        },
    )


def _anti_overfit_check(backtest: dict[str, Any], optimization: dict[str, Any]) -> dict[str, Any]:
    splits = (backtest.get("strategy_family_summary") or {}).get("time_series_splits") or {}
    temporal = optimization.get("temporal_guard") or {}
    complete = (
        temporal.get("status") == "pass"
        and splits.get("random_split_allowed") is False
        and splits.get("future_data_allowed_in_signal") is False
        and bool(splits.get("train_quarters"))
        and bool(splits.get("validation_quarters"))
        and bool(splits.get("out_of_sample_quarters"))
        and splits.get("production_ready") is False
    )
    return _check(
        "anti_future_overfit_guard",
        "防未来函数与过拟合门禁",
        complete,
        "报告已区分训练/验证/样本外季度代理，禁止随机切分；真实 walk-forward 仍未完成。",
        {
            "temporal_guard": temporal.get("status"),
            "split_status": splits.get("status"),
            "train_quarters": splits.get("train_quarters"),
            "validation_quarters": splits.get("validation_quarters"),
            "out_of_sample_quarters": splits.get("out_of_sample_quarters"),
            "production_ready": splits.get("production_ready"),
        },
    )


def _frontend_check(root: Path) -> dict[str, Any]:
    family_strip = root / "frontend" / "src" / "features" / "workspace-shared" / "FamilyStrip.tsx"
    quality_helper = root / "frontend" / "src" / "features" / "workspace-shared" / "workspaceFamilyQuality.ts"
    family_text = family_strip.read_text(encoding="utf-8") if family_strip.exists() else ""
    helper_text = quality_helper.read_text(encoding="utf-8") if quality_helper.exists() else ""
    complete = (
        "Modal" in family_text
        and "fallback" in family_text
        and "弱数据候选" in family_text
        and "familyStripQualityText" in helper_text
    )
    return _check(
        "frontend_family_dense_display",
        "前端策略族高密度展示",
        complete,
        "策略族概览保持高密度，详情进入只读弹窗，并展示 data_quality/fallback/缺失数据提示。",
        {
            "family_strip_component": str(family_strip.relative_to(root)),
            "quality_helper": str(quality_helper.relative_to(root)),
            "modal_detail": "Modal" in family_text,
        },
    )


def _safety_check(optimization: dict[str, Any], settings: AppSettings) -> dict[str, Any]:
    executive = optimization.get("executive_conclusion") or {}
    complete = (
        executive.get("can_connect_to_production_chain") is False
        and executive.get("production_parameter_change_allowed") is False
        and not settings.main_force_model_ranking_enabled
        and not settings.main_force_model_paper_suggestion_enabled
    )
    return _check(
        "no_ranking_or_trade_execution_effect",
        "不影响排序与交易执行",
        complete,
        "默认不改变原有策略排序、不写生产参数、不触发真实交易执行。",
        {
            "can_connect_to_production_chain": executive.get("can_connect_to_production_chain"),
            "production_parameter_change_allowed": executive.get("production_parameter_change_allowed"),
            "main_force_ranking_enabled_default": settings.main_force_model_ranking_enabled,
            "paper_suggestion_enabled_default": settings.main_force_model_paper_suggestion_enabled,
        },
    )


def _production_blockers(sources: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for gate in (sources["optimization"].get("executive_conclusion") or {}).get("blocking_gates") or []:
        blockers.append(
            {
                "source": "optimization_gate",
                "key": str(gate.get("key") or gate.get("gate") or "unknown_gate"),
                "reason": str(gate.get("message") or gate.get("status") or "blocking"),
            }
        )
    splits = (sources["backtest"].get("strategy_family_summary") or {}).get("time_series_splits") or {}
    for item in splits.get("promotion_blockers") or []:
        blockers.append({"source": "strategy_family_split", "key": str(item), "reason": "策略族仍未完成真实生产晋级验证。"})
    main_shadow = sources["closed_loop"].get("main_force_model_shadow") or {}
    for item in main_shadow.get("promotion_blockers") or []:
        blockers.append({"source": "main_force_shadow", "key": str(item), "reason": "主力模型 Shadow 样本或效果未达标。"})
    exit_shadow = sources["closed_loop"].get("auxiliary_model_shadow") or {}
    for item in exit_shadow.get("promotion_blockers") or []:
        blockers.append({"source": "exit_model_shadow", "key": str(item), "reason": "止盈止损辅助模型 Shadow 样本未达标。"})
    for source_key in ("focus_parameter_walk_forward", "market_state_guard_walk_forward", "exit_parameter_walk_forward"):
        for item in (sources.get(source_key) or {}).get("promotion_blockers") or []:
            blockers.append({"source": source_key, "key": str(item), "reason": "已有局部 OOS 证据，但仍未满足生产晋级门禁。"})
    return blockers


def _check(key: str, title: str, complete: bool, summary: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "status": "pass" if complete else "fail",
        "complete": bool(complete),
        "summary": summary,
        "evidence": evidence,
    }


def _check_complete(checks: list[dict[str, Any]], key: str) -> bool:
    return any(item["key"] == key and item["complete"] for item in checks)


def _read_sources(root: Path, report_date: str) -> dict[str, Any]:
    report_dir = root / "docs" / "reports"
    return {
        "backtest": _load_json(report_dir / f"strategy-24m-backtest-{report_date}.json"),
        "optimization": _load_json(report_dir / f"strategy-24m-optimization-report-{report_date}.json"),
        "closed_loop": _load_json(report_dir / f"strategy-improvement-closed-loop-{report_date}.json"),
        "main_force": _load_json(report_dir / f"main-force-model-production-readiness-{report_date}.json"),
        "focus_walk_forward_plan": _load_optional_json(report_dir / f"focus-strategy-walk-forward-plan-{report_date}" / "summary.json"),
        "focus_parameter_walk_forward": _load_optional_json(report_dir / f"focus-strategy-parameter-walk-forward-{report_date}" / "summary.json"),
        "market_state_guard_walk_forward": _load_optional_json(report_dir / f"market-state-guard-walk-forward-{report_date}" / "summary.json"),
        "exit_parameter_walk_forward": _load_optional_json(report_dir / f"exit-parameter-walk-forward-{report_date}" / "summary.json"),
        "focus_purged_gap_audit": _load_optional_json(report_dir / f"focus-strategy-purged-gap-audit-{report_date}" / "summary.json"),
    }


def _source_files(report_date: str) -> dict[str, str]:
    return {
        "backtest": f"docs/reports/strategy-24m-backtest-{report_date}.json",
        "optimization": f"docs/reports/strategy-24m-optimization-report-{report_date}.json",
        "closed_loop": f"docs/reports/strategy-improvement-closed-loop-{report_date}.json",
        "main_force": f"docs/reports/main-force-model-production-readiness-{report_date}.json",
        "focus_parameter_walk_forward": f"docs/reports/focus-strategy-parameter-walk-forward-{report_date}/summary.json",
        "exit_parameter_walk_forward": f"docs/reports/exit-parameter-walk-forward-{report_date}/summary.json",
        "market_state_guard_walk_forward": f"docs/reports/market-state-guard-walk-forward-{report_date}/summary.json",
        "focus_purged_gap_audit": f"docs/reports/focus-strategy-purged-gap-audit-{report_date}/summary.json",
        "requirements_plan": "docs/strategy-system-consolidation-and-enhancement-development-plan.md",
    }


def _requirements_source_check(root: Path) -> dict[str, Any]:
    path = root / "docs" / "strategy-system-consolidation-and-enhancement-development-plan.md"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    required = ("P0", "P1", "P2", "P3", "生产放行门禁", "只读/Shadow")
    missing = [item for item in required if item not in text]
    return _check(
        "requirements_source_document",
        "需求源与验收边界",
        path.exists() and not missing,
        "需求文档已补齐，并明确最小只读/Shadow 闭环与真实交易生产放行门禁的边界。",
        {"path": str(path.relative_to(root)), "missing_markers": missing},
    )


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def _load_optional_json(path: Path) -> dict[str, Any]:
    return _load_json(path) if path.exists() else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _yes_no(value: bool) -> str:
    return "是" if value else "否"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build strategy system acceptance report.")
    parser.add_argument("--date", default=SOURCE_DATE)
    parser.add_argument("--json-output", default="")
    parser.add_argument("--markdown-output", default="")
    args = parser.parse_args()
    report = build_report(report_date=args.date, root=ROOT)
    json_output = Path(args.json_output) if args.json_output else ROOT / "docs" / "reports" / f"strategy-system-acceptance-report-{args.date}.json"
    md_output = Path(args.markdown_output) if args.markdown_output else ROOT / "docs" / "reports" / f"strategy-system-acceptance-report-{args.date}.md"
    _write_json(json_output, report)
    md_output.parent.mkdir(parents=True, exist_ok=True)
    md_output.write_text(render_markdown(report), encoding="utf-8")
    print(f"wrote {json_output}")
    print(f"wrote {md_output}")
    print(json.dumps({"overall_status": report["overall_status"], "completion_pct": report["completion_pct"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
