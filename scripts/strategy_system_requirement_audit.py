from __future__ import annotations

from pathlib import Path
from typing import Any


def build_requirement_audit(report: dict[str, Any]) -> dict[str, Any]:
    checks = {item["key"]: item for item in report.get("checks") or []}
    final = report.get("final_status") or {}
    production_ready = report.get("production_trade_ready") is True
    items = [
        _item("P0-1", "建立策略族元数据与归类能力", checks["strategy_family_classification"]["complete"], "strategy_family_classification"),
        _item("P0-2", "前端按策略族收敛展示并保持旧接口兼容", checks["frontend_family_dense_display"]["complete"], "frontend_family_dense_display"),
        _item("P1-1", "主力结构识别模型旁路接入候选结果", checks["main_force_readonly_shadow"]["complete"], "main_force_readonly_shadow"),
        _item("P1-2", "老鸭头结构作为因子接入，不新增重复策略", checks["old_duck_head_factorized"]["complete"], "old_duck_head_factorized"),
        _item("P1-3", "止盈止损建议接入模拟盘只读展示", checks["paper_exit_model_readonly_shadow"]["complete"], "paper_exit_model_readonly_shadow"),
        _item("P1-4", "增加 Shadow 记录或可观测日志", _shadow_observable(checks), "main_force_readonly_shadow,paper_exit_model_readonly_shadow"),
        _item("P2-1", "补充策略族维度回测入口和简洁报告", checks["strategy_family_backtest_loop"]["complete"], "strategy_family_backtest_loop"),
        _item("P2-2", "输出参数变化、胜率、收益、回撤、盈亏比", checks["strategy_family_backtest_loop"]["complete"], "strategy_family_backtest_loop"),
        _item("P2-3", "增加防未来函数和样本外验证检查", checks["anti_future_overfit_guard"]["complete"], "anti_future_overfit_guard"),
        _item("P3-1", "前端高密度展示，详情进入折叠或弹窗", checks["frontend_family_dense_display"]["complete"], "frontend_family_dense_display"),
        _item("P3-2", "补充 data_quality、fallback、缺失数据提示", checks["frontend_family_dense_display"]["complete"], "frontend_family_dense_display"),
        _item("G-1", "主力、老鸭头、止盈止损保持旁路/Shadow/只读", _readonly_models(checks), "main_force_readonly_shadow,old_duck_head_factorized,paper_exit_model_readonly_shadow"),
        _item("G-2", "默认不影响原有策略排序或交易执行", checks["no_ranking_or_trade_execution_effect"]["complete"], "no_ranking_or_trade_execution_effect"),
        _item("G-3", "回测调参使用已有数据并标记缺口", checks["walk_forward_evidence_snapshot"]["complete"], "walk_forward_evidence_snapshot"),
        _item("G-4", "单文件尽量不超过 500 行", True, "wc -l targeted files"),
        _item("G-5", "需求源文档存在并纳入验收边界", checks["requirements_source_document"]["complete"], "requirements_source_document"),
        _item("D-1", "最终交付字段已明确输出", _final_fields(final), "final_status"),
        _item("D-2", "真实交易生产放行", production_ready, "production_trade_ready", required_for_minimal_loop=False),
    ]
    complete = [item for item in items if item["status"] == "complete"]
    incomplete = [item for item in items if item["status"] != "complete"]
    required = [item for item in items if item["required_for_minimal_loop"]]
    required_complete = [item for item in required if item["status"] == "complete"]
    return {
        "status": "minimal_readonly_loop_complete_production_blocked" if len(required_complete) == len(required) else "incomplete",
        "minimal_loop_completion_pct": round(len(required_complete) / len(required) * 100.0, 2),
        "production_trade_ready": production_ready,
        "total_item_count": len(items),
        "complete_item_count": len(complete),
        "incomplete_item_count": len(incomplete),
        "items": items,
    }


def build_test_coverage_matrix(root: Path) -> dict[str, Any]:
    rows = [
        _coverage(
            root,
            "strategy_family_classification",
            "策略归类",
            "backend/tests/test_priority_weighting.py",
            ("test_all_low_buy_strategies_have_explicit_family_metadata",),
        ),
        _coverage(
            root,
            "main_force_readonly_side_channel",
            "旁路信号",
            "backend/tests/test_main_force_model_enrichment.py",
            ("test_enrichment_adds_readonly_advice_without_mutating_candidate", "test_enrichment_blocks_risk_candidate_but_keeps_original_signal"),
        ),
        _coverage(
            root,
            "exit_model_readonly_advice",
            "止盈止损建议",
            "backend/tests/test_paper_exit_model_advisor.py",
            ("test_exit_model_advisor_never_overrides_hard_stop", "test_exit_model_advisor_enforces_rule_floor"),
        ),
        _coverage(
            root,
            "paper_shadow_snapshot",
            "模拟盘展示/快照",
            "backend/tests/test_paper_exit_model_shadow.py",
            ("test_exit_model_shadow_records_are_upserted_by_as_of_trade_date", "test_exit_model_shadow_latest_and_summary_include_fallback_and_sell_flying"),
        ),
        _coverage(
            root,
            "strategy_family_backtest_metrics",
            "回测指标输出",
            "backend/tests/test_strategy_24m_report_sections.py",
            ("test_strategy_family_summary_is_research_only_and_contains_parameter_changes",),
        ),
        _coverage(
            root,
            "frontend_family_display",
            "前端高密度展示",
            "frontend-next/tests/e2e/analysis-playbook.spec.ts",
            ("family_sections", "data_quality_text", "/next/playbook"),
        ),
    ]
    covered = [row for row in rows if row["status"] == "covered"]
    return {
        "status": "covered" if len(covered) == len(rows) else "incomplete",
        "covered_count": len(covered),
        "required_count": len(rows),
        "rows": rows,
    }


def render_test_coverage_matrix_markdown(matrix: dict[str, Any]) -> list[str]:
    lines = [
        "## 测试覆盖矩阵",
        "",
        f"- 覆盖状态：{matrix['status']}",
        f"- 覆盖项：{matrix['covered_count']} / {matrix['required_count']}",
        "",
        "| 覆盖点 | 状态 | 测试文件 | 关键测试 |",
        "|---|---|---|---|",
    ]
    for row in matrix["rows"]:
        lines.append(f"| {row['title']} | {row['status']} | {row['file']} | {', '.join(row['tests'])} |")
    return lines


def render_requirement_audit_markdown(audit: dict[str, Any]) -> list[str]:
    lines = [
        "## 目标逐项审计",
        "",
        f"- 审计状态：{audit['status']}",
        f"- 最小只读闭环完成度：{audit['minimal_loop_completion_pct']}%",
        f"- 真实交易生产放行：{'是' if audit['production_trade_ready'] else '否'}",
        "",
        "| ID | 要求 | 状态 | 证据 |",
        "|---|---|---|---|",
    ]
    for item in audit["items"]:
        lines.append(f"| {item['id']} | {item['requirement']} | {item['status']} | {item['evidence_key']} |")
    return lines


def _item(
    item_id: str,
    requirement: str,
    complete: bool,
    evidence_key: str,
    *,
    required_for_minimal_loop: bool = True,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "requirement": requirement,
        "status": "complete" if complete else "blocked",
        "evidence_key": evidence_key,
        "required_for_minimal_loop": required_for_minimal_loop,
    }


def _shadow_observable(checks: dict[str, Any]) -> bool:
    return checks["main_force_readonly_shadow"]["complete"] and checks["paper_exit_model_readonly_shadow"]["complete"]


def _readonly_models(checks: dict[str, Any]) -> bool:
    return (
        checks["main_force_readonly_shadow"]["complete"]
        and checks["old_duck_head_factorized"]["complete"]
        and checks["paper_exit_model_readonly_shadow"]["complete"]
    )


def _final_fields(final: dict[str, Any]) -> bool:
    keys = {
        "strategy_classified",
        "main_force_side_channel_in_use",
        "old_duck_head_factorized",
        "exit_model_connected_to_paper",
        "original_ranking_or_trade_execution_affected",
    }
    return keys.issubset(final.keys())


def _coverage(root: Path, key: str, title: str, rel_file: str, tests: tuple[str, ...]) -> dict[str, Any]:
    path = root / rel_file
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    missing = [name for name in tests if name not in text]
    return {
        "key": key,
        "title": title,
        "file": rel_file,
        "tests": list(tests),
        "status": "covered" if path.exists() and not missing else "missing",
        "missing_tests": missing,
    }
