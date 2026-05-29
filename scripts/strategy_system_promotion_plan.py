from __future__ import annotations

from typing import Any


_PLAN_TEMPLATES: dict[str, dict[str, Any]] = {
    "data_gate": {
        "title": "补齐 ETF T0 分钟线与执行元数据",
        "requires_external_data": True,
        "estimated_effort": "1-3 天，取决于 Tushare/交易所/供应商分钟线可用性",
        "next_commands": [
            "TUSHARE_TOKEN=... PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/backfill_etf_minute_history.py --scope t0-etf --period 5m --allow-partial",
            "PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/backfill_instrument_metadata.py --scope all-stock",
            "PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/backfill_daily_limit_prices.py --derive-pre-close",
        ],
        "acceptance_evidence": [
            "etf_t0_minute_coverage.status=pass",
            "market_metadata_coverage.status=pass",
            "minute_bar_snapshots bid/ask spread, premium/discount, tracking index, liquidity tier fresh coverage >= threshold",
        ],
    },
    "strategy_family_walk_forward": {
        "title": "补齐策略族真实 walk-forward 与 purged-gap",
        "requires_external_data": False,
        "estimated_effort": "0.5-1 天，基于现有 24M 日线与已落盘矩阵",
        "next_commands": [
            "PYTHONPATH=backend:. backend/.venv/bin/python scripts/strategy_24m_walk_forward_matrix.py --date 2026-05-28 --purged-gap-days 10",
            "PYTHONPATH=backend:. backend/.venv/bin/python scripts/focus_strategy_parameter_walk_forward_summary.py --date 2026-05-28",
        ],
        "acceptance_evidence": [
            "true_strategy_family_walk_forward_not_executed absent",
            "purged_gap_not_executed absent",
            "all candidate families have train/validation/OOS windows",
        ],
    },
    "main_force_shadow": {
        "title": "积累主力模型线上 Shadow settled 样本",
        "requires_external_data": False,
        "estimated_effort": "至少 2-4 周自然交易日观察",
        "next_commands": [
            "PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/main_force_shadow_warmup.py --date 2026-05-28",
            "PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/main_force_model_backtest.py --date 2026-05-28",
        ],
        "acceptance_evidence": [
            "shadow_record_count >= 300",
            "settled_shadow_count >= 120",
            "success_rate and profit_factor pass configured thresholds",
        ],
    },
    "exit_model_shadow": {
        "title": "积累退出模型 Shadow settled 样本",
        "requires_external_data": False,
        "estimated_effort": "至少 1-2 周模拟盘持仓观察",
        "next_commands": [
            "PYTHONPATH=backend:. backend/.venv/bin/python research/scripts/evaluate_exit_model_shadow.py",
            "PYTHONPATH=backend:. backend/.venv/bin/python scripts/exit_parameter_walk_forward_summary.py --date 2026-05-28",
        ],
        "acceptance_evidence": [
            "shadow_record_count >= 30",
            "settled_shadow_count >= 30",
            "hard_stop override remains forbidden",
        ],
    },
    "focus_parameter": {
        "title": "补全重点策略参数稳定性与 Shadow 验证",
        "requires_external_data": False,
        "estimated_effort": "0.5-1 天，若只复用既有矩阵；更久取决于新增参数网格",
        "next_commands": [
            "PYTHONPATH=backend:. backend/.venv/bin/python scripts/focus_strategy_parameter_walk_forward_summary.py --date 2026-05-28",
            "PYTHONPATH=backend:. backend/.venv/bin/python scripts/strategy_24m_parameter_plans.py --date 2026-05-28",
        ],
        "acceptance_evidence": [
            "purged_gap_candidate_grid_not_executed absent",
            "strategy_specific_window_not_all_passed absent or documented as research-only",
            "online_shadow_settled_sample_lt_required absent",
        ],
    },
    "market_state_guard": {
        "title": "重测市场状态保护参数稳定性",
        "requires_external_data": False,
        "estimated_effort": "0.5 天",
        "next_commands": [
            "PYTHONPATH=backend:. backend/.venv/bin/python scripts/market_state_guard_walk_forward_summary.py --date 2026-05-28",
        ],
        "acceptance_evidence": [
            "market_state_guard_not_consistently_better_than_current absent",
            "pass rate stable across OOS windows",
        ],
    },
}

_SOURCE_TO_GROUP = {
    "optimization_gate": "data_gate",
    "strategy_family_split": "strategy_family_walk_forward",
    "main_force_shadow": "main_force_shadow",
    "exit_model_shadow": "exit_model_shadow",
    "focus_parameter_walk_forward": "focus_parameter",
    "market_state_guard_walk_forward": "market_state_guard",
    "exit_parameter_walk_forward": "exit_model_shadow",
}


def build_promotion_action_plan(blockers: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, dict[str, Any]] = {}
    for blocker in blockers:
        group_key = _SOURCE_TO_GROUP.get(str(blocker.get("source")), "other")
        template = _PLAN_TEMPLATES.get(group_key, _fallback_template(group_key))
        row = grouped.setdefault(
            group_key,
            {
                "key": group_key,
                **template,
                "blockers": [],
            },
        )
        row["blockers"].append(blocker)

    actions = sorted(grouped.values(), key=lambda row: (not row["requires_external_data"], row["key"]))
    return {
        "status": "blocked_by_production_gates" if actions else "ready",
        "action_count": len(actions),
        "requires_external_data_count": sum(1 for row in actions if row["requires_external_data"]),
        "actions": actions,
    }


def render_promotion_action_plan_markdown(plan: dict[str, Any]) -> list[str]:
    lines = [
        "## 生产放行动作计划",
        "",
        f"- 状态：{plan['status']}",
        f"- 动作数：{plan['action_count']}",
        f"- 需要外部数据的动作数：{plan['requires_external_data_count']}",
        "",
        "| 动作 | 外部数据 | 预计耗时 | 阻断项 | 下一步命令 |",
        "|---|---|---|---|---|",
    ]
    for row in plan["actions"]:
        blocker_keys = ", ".join(sorted({str(item.get("key")) for item in row["blockers"]}))
        lines.append(
            f"| {row['title']} | {'是' if row['requires_external_data'] else '否'} | "
            f"{row['estimated_effort']} | {blocker_keys} | {row['next_commands'][0]} |"
        )
    return lines


def _fallback_template(group_key: str) -> dict[str, Any]:
    return {
        "title": group_key,
        "requires_external_data": False,
        "estimated_effort": "待确认",
        "next_commands": ["人工确认阻断来源后补充命令"],
        "acceptance_evidence": ["阻断项消失或转为 documented research-only"],
    }
