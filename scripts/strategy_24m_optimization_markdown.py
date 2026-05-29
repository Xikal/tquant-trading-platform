"""Markdown rendering for the 24-month strategy optimization report."""

from __future__ import annotations

import json
from typing import Any


def _pct(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return str(value)


def _num(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return str(value)


def _gate_name(gate: dict[str, Any]) -> str:
    return str(gate.get("gate") or gate.get("key") or gate.get("name") or "unknown_gate")


def _gate_blocking(gate: dict[str, Any]) -> bool:
    if "blocking" in gate:
        return bool(gate.get("blocking"))
    return gate.get("severity") == "blocking" and gate.get("status") != "pass"


def _gate_reason(gate: dict[str, Any]) -> str:
    return str(gate.get("reason") or gate.get("message") or "")


def _sector_summary(item: dict[str, Any]) -> str:
    breakdown = item.get("sector_breakdown") or {}
    rows = breakdown.get("rows") or []
    if not rows:
        return str(breakdown.get("reason") or "无可展示行业归因")
    top = rows[0]
    return (
        f"{top.get('title') or top.get('key')} "
        f"sample={top.get('sample_count')} filled={top.get('filled_count')} "
        f"PF={_num(top.get('profit_factor'))} MDD={_pct(top.get('max_drawdown_pct'))}; "
        f"mapped={breakdown.get('mapped_rate_pct')}%; {breakdown.get('production_caveat', '')}"
    )


def _walk_forward_summary(item: dict[str, Any]) -> str:
    wf = item.get("walk_forward_validation") or {}
    grid = wf.get("parameter_grid") or []
    names = [str(row.get("name")) for row in grid[:4] if row.get("name")]
    suffix = ", ..." if len(grid) > 4 else ""
    return (
        f"{wf.get('status')} windows={wf.get('window_count')} "
        f"purged_gap={wf.get('purged_gap_days')}d "
        f"grid={'; '.join(names)}{suffix}"
    )


def _scope_metrics_summary(metrics: dict[str, Any]) -> str:
    keys = [
        "strategy_count",
        "coverage_pct",
        "eligible_profile_count",
        "accepted_symbol_count",
        "sample_count",
        "settled_count",
        "record_count",
        "oos_promotion_ready",
        "walk_forward_passed",
        "walk_forward_windows",
        "signal_count",
        "washout_signal_count",
        "preset_count",
    ]
    parts = [f"{key}={metrics.get(key)}" for key in keys if key in metrics]
    return ", ".join(parts) if parts else "{}"


def render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# {report['title']}")
    lines.append("")
    lines.append(f"- 生成时间：{report['generated_at']}")
    lines.append(f"- 数据源日期：{report['source_date']}")
    window = report["scope"].get("actual_evaluation_window") or {}
    lines.append(
        f"- 评估窗口：{window.get('start')} 至 {window.get('end')}，交易日 {window.get('trade_days')}"
    )
    lines.append(f"- 策略数量：{report['scope']['strategy_count']}")
    lines.append("")
    lines.append("## 一、总论")
    conclusion = report["executive_conclusion"]
    lines.append("")
    lines.append(f"- 是否可接入生产链路：{'是' if conclusion['can_connect_to_production_chain'] else '否'}")
    lines.append(
        f"- 是否允许生产参数变更：{'是' if conclusion['production_parameter_change_allowed'] else '否'}"
    )
    lines.append(f"- 原因：{conclusion['reason']}")
    lines.append("")
    lines.append("## 二、保留/降权/暂停/晋级清单")
    lines.append("")
    decisions = report["strategy_decisions"]
    for label, key in [
        ("保留当前层级", "retain_current_layer"),
        ("降权或降级观察", "downgrade_or_reduce_weight"),
        ("暂停或降权生产权重", "pause"),
        ("可生产晋级", "promote_to_production"),
        ("仅 Paper/Shadow 观察", "paper_or_shadow_observe"),
    ]:
        values = decisions.get(key) or []
        lines.append(f"- {label}：{', '.join(values) if values else '无'}")
    lines.append("")
    lines.append("## 二点五、平台策略与模型覆盖清单")
    lines.append("")
    coverage = report.get("scope_coverage") or {}
    lines.append(
        f"- 覆盖项：{coverage.get('item_count')}，生产可用项：{coverage.get('production_eligible_item_count')}"
    )
    lines.append("| 范围 | 入口 | 状态 | 覆盖策略/模型 | 关键指标 | 生产可用 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for item in coverage.get("items", []) or []:
        lines.append(
            "| {title} | {surface} | {status} | {keys} | {metrics} | {eligible} |".format(
                title=item.get("title"),
                surface=item.get("surface"),
                status=item.get("status"),
                keys=", ".join(item.get("covered_strategy_keys") or []),
                metrics=_scope_metrics_summary(item.get("metrics") or {}),
                eligible="是" if item.get("production_eligible") else "否",
            )
        )
    gaps = coverage.get("coverage_gaps") or []
    if gaps:
        lines.append(f"- 覆盖阻断：{'; '.join(gaps[:12])}{' ...' if len(gaps) > 12 else ''}")
    lines.append("")
    lines.append("## 三、策略指标与审查结论")
    lines.append("")
    lines.append(
        "| 策略 | 层级 | 样本 | 胜率 | PF | 均笔 | 最大回撤 | 建议 | 过拟合风险 |"
    )
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |")
    for item in report["strategy_items"]:
        metrics = item["before_metrics"]
        lines.append(
            "| {key} | {layer} | {sample} | {win} | {pf} | {avg} | {mdd} | {rec} | {risk} |".format(
                key=item["strategy_key"],
                layer=item["policy_layer"],
                sample=metrics.get("sample_count"),
                win=_pct(metrics.get("win_rate_pct")),
                pf=_num(metrics.get("profit_factor")),
                avg=_pct(metrics.get("avg_trade_return_pct")),
                mdd=_pct(metrics.get("max_drawdown_pct")),
                rec=item["review_recommendation"],
                risk=item["overfit_risk_level"],
            )
        )
    lines.append("")
    family_summary = report.get("strategy_family_summary") or {}
    families = family_summary.get("families") or []
    splits = family_summary.get("time_series_splits") or {}
    lines.append("## 三点五、策略族闭环")
    lines.append("")
    lines.append(
        f"- 状态：{family_summary.get('status', 'research_only')}，"
        f"策略族 {family_summary.get('family_count', len(families))} 个，"
        f"覆盖策略 {family_summary.get('strategy_count', 0)} 个；"
        f"排序影响={family_summary.get('sorting_effect', 'none')}，"
        f"生产参数变更={'允许' if family_summary.get('production_parameter_change_allowed') else '不允许'}。"
    )
    lines.append(
        "- 训练/验证/样本外：train={train}；validation={validation}；oos={oos}；"
        "证据={status}；production_ready={ready}。".format(
            train=", ".join(splits.get("train_quarters") or []) or "-",
            validation=", ".join(splits.get("validation_quarters") or []) or "-",
            oos=", ".join(splits.get("out_of_sample_quarters") or []) or "-",
            status=splits.get("status", "missing_quarter_breakdown"),
            ready=str(bool(splits.get("production_ready"))).lower(),
        )
    )
    lines.append("| 策略族 | 策略 | 胜率 | PF | 总收益 | 最大回撤 | 验证状态 |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | --- |")
    for item in families:
        lines.append(
            "| {title} | {strategies} | {win} | {pf} | {ret} | {mdd} | {status} |".format(
                title=item.get("title"),
                strategies=", ".join(item.get("strategy_keys") or []),
                win=_pct(item.get("win_rate_pct")),
                pf=_num(item.get("profit_factor")),
                ret=_pct(item.get("total_return_pct")),
                mdd=_pct(item.get("max_drawdown_pct")),
                status=item.get("validation_status"),
            )
        )
    lines.append("")
    lines.append("## 四、参数审查口径")
    lines.append("")
    lines.append(
        "- 所有策略的 `optimized_parameters.optimized_values_for_production` 均保持等于当前生产默认值。"
    )
    lines.append(
        "- `candidate_overrides_for_shadow_or_walk_forward` 只表示可进入 Shadow 或 walk-forward 的候选范围，不代表已优化完成。"
    )
    lines.append(
        "- 本轮没有把回测收益直接写入生产参数；候选参数必须先通过时序 walk-forward、purged gap、稳定性和 Shadow。"
    )
    policy = report.get("metric_interpretation_policy") or {}
    research_only = policy.get("research_only_metrics") or {}
    if research_only:
        lines.append(
            "- `spike_return_*` / `avg_max_gain_5d` 属于未来窗口最高价观察指标，只能判断冲高机会，不能作为可成交收益或生产晋级指标。"
        )
        lines.append(
            "- `diagnostic_compound_return_pct` 是逐信号连续复利诊断字段，不是真实账户资金曲线。"
        )
        lines.append(f"- 资金曲线限制：{policy.get('capital_curve_caveat')}")
    lines.append("")
    for item in report["strategy_items"]:
        changed = item.get("changed_parameters") or {}
        lines.append(f"### {item['strategy_key']}")
        lines.append("")
        lines.append(f"- 当前层级：{item['policy_layer']} / {item['policy_tier']}")
        lines.append(f"- 当前建议：{item['review_recommendation']}")
        lines.append(f"- 治理状态：{item.get('governance_state')}")
        lines.append(f"- 调参建议：{json.dumps(changed, ensure_ascii=False) if changed else '无生产调参；保持当前参数'}")
        lines.append(f"- walk-forward：{item['walk_forward_validation']['status']}")
        lines.append(f"- walk-forward 验收矩阵：{_walk_forward_summary(item)}")
        lines.append(f"- purged gap：{item['purged_gap_validation']['status']}")
        lines.append(f"- 未来函数风险：{item['future_function_risk']['risk_level']}")
        signal = item.get("buy_signal_diagnosis") or {}
        lines.append(f"- 买入信号诊断：{signal.get('explanation')}")
        lines.append(f"- 过拟合标记：{', '.join(item['overfit_flags']) if item['overfit_flags'] else 'none'}")
        related = item.get("related_capital_limited_metrics")
        if related:
            lines.append(f"- 相关资金约束回测：{json.dumps(related, ensure_ascii=False)}")
        lines.append(f"- 静态行业归因摘要：{_sector_summary(item)}")
        missing = item.get("missing_required_metrics") or []
        if missing:
            lines.append(f"- 生产前缺失指标：{', '.join(missing)}")
        lines.append("")
    lines.append("## 五、新增模型结论")
    lines.append("")
    main_force = report["models"]["main_force_model"]
    exit_model = report["models"]["exit_model"]
    next_day = report["models"]["next_day_event_model"]
    lines.append(f"- 主力模型：{main_force['production_conclusion']}")
    lines.append(f"- 主力模型离线指标：{json.dumps(main_force.get('oos_metrics'), ensure_ascii=False)}")
    lines.append(
        f"- 主力模型 OOS 阻断：{', '.join(main_force.get('oos_promotion_blockers') or []) or '无'}"
    )
    lines.append(f"- 主力模型 OOS 证据：{main_force.get('oos_evidence_status')}，{main_force.get('oos_evidence_caveat')}")
    lines.append(f"- 主力模型 Shadow：{json.dumps(main_force.get('shadow_gate'), ensure_ascii=False)}")
    lines.append(f"- 退出模型：{exit_model['production_conclusion']}")
    lines.append(f"- 退出模型样本：record={exit_model.get('record_count')} settled={exit_model.get('settled_count')}")
    exit_wf = report.get("exit_parameter_walk_forward") or {}
    if exit_wf:
        delta = exit_wf.get("aggregate_delta") or {}
        lines.append(
            "- 退出参数 walk-forward："
            f"{exit_wf.get('passed_window_count')}/{exit_wf.get('window_count')} 窗口通过，"
            f"平均 PF 改善 {delta.get('avg_delta_profit_factor')}，"
            f"平均回撤改善 {delta.get('avg_delta_max_drawdown_pct')}pct，"
            f"Shadow 候选={'是' if exit_wf.get('shadow_candidate') else '否'}，生产可用=否。"
        )
    evidence = report.get("exit_parameter_shadow_evidence") or {}
    best_exit = evidence.get("best_by_profit_factor") or {}
    if best_exit:
        lines.append(
            "- 止盈止损候选矩阵："
            f"{best_exit.get('variant_key')} 暂列 PF 最优，"
            f"coverage={evidence.get('coverage_pct')}%，"
            "仅 Shadow/完整 walk-forward 复验，不能写生产。"
        )
    market_wf = report.get("market_state_guard_walk_forward") or {}
    if market_wf:
        delta = market_wf.get("aggregate_delta") or {}
        lines.append(
            "- 市场状态保护候选："
            f"{market_wf.get('variant_under_test')} 已完成 "
            f"{market_wf.get('completed_window_count')}/{market_wf.get('planned_window_count')} 窗口，"
            f"通过 {market_wf.get('passed_window_count')}/{market_wf.get('window_count')}，"
            f"平均 PF 差 {delta.get('avg_delta_profit_factor')}，"
            f"平均收益差 {delta.get('avg_delta_total_return_pct')}pct，"
            f"平均回撤差 {delta.get('avg_delta_max_drawdown_pct')}pct；"
            "不能写生产。"
        )
    focus_wf = report.get("focus_parameter_walk_forward") or {}
    if focus_wf:
        findings = focus_wf.get("aggregate_findings") or {}
        combined = focus_wf.get("combined") or {}
        lines.append(
            "- P1 核心策略参数窄网格："
            f"矩阵窗口 {focus_wf.get('scope', {}).get('total_matrix_window_count')} 个，"
            f"合并口径通过 {combined.get('passed_window_count')}/{combined.get('window_count')}；"
            f"first_board 通过 {findings.get('strategy_pass_counts', {}).get('first_board')}/7，"
            f"volume_shrink 通过 {findings.get('strategy_pass_counts', {}).get('volume_shrink')}/7；"
            f"{findings.get('profit_mechanism')} 生产可用=否。"
        )
    lines.append(f"- 次日事件模型：{next_day['production_conclusion']}")
    lines.append("")
    lines.append("## 六、数据闸门")
    lines.append("")
    for gate in report["data_gates"]["gates"]:
        lines.append(
            f"- {_gate_name(gate)}：{gate.get('status')}，"
            f"blocking={_gate_blocking(gate)}，{_gate_reason(gate)}"
        )
    lines.append("")
    lines.append("## 七、GPU / Go / Rust")
    lines.append("")
    acc = report["acceleration"]
    lines.append(f"- GPU：未使用，{acc['gpu_reason']}")
    lines.append(f"- Go/Rust：未新增使用，{acc['go_rust_reason']}")
    lines.append(
        f"- Profiling：scope={acc.get('profile_scope')}，"
        f"bottleneck={acc.get('profile_bottleneck_step')} "
        f"{acc.get('profile_bottleneck_avg_ms')}ms"
    )
    parity = acc.get("existing_rust_parity") or {}
    if parity:
        lines.append(
            f"- 既有 Rust parity：{parity.get('status')}，"
            f"{parity.get('test_file')}，metrics={', '.join(parity.get('covered_metrics') or [])}"
        )
    candidates = acc.get("candidate_future_go_rust_modules") or []
    if candidates:
        lines.append(f"- 后续可 profile 的 Go/Rust 候选模块：{', '.join(candidates)}")
    lines.append("")
    lines.append("## 八、未完成项")
    lines.append("")
    for item in report["unfinished_items"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 九、测试命令与结果")
    lines.append("")
    tests = report.get("tests", {})
    lines.append("### 命令")
    lines.append("")
    for command in tests.get("planned_commands", []) or []:
        lines.append(f"- `{command}`")
    lines.append("")
    lines.append("### 结果")
    lines.append("")
    results = tests.get("results", []) or []
    if results:
        for result in results:
            if isinstance(result, dict):
                lines.append(
                    f"- {result.get('status', 'recorded')}：{result.get('summary') or result.get('command')}"
                )
            else:
                lines.append(f"- {result}")
    else:
        lines.append("- 尚未写入本报告；以执行终端结果为准。")
    lines.append("")
    lines.append("## 十、报告文件")
    lines.append("")
    lines.append(
        f"- Markdown：docs/reports/strategy-24m-optimization-report-{report['report_date']}.md"
    )
    lines.append(
        f"- JSON：docs/reports/strategy-24m-optimization-report-{report['report_date']}.json"
    )
    lines.append("")
    return "\n".join(lines)
