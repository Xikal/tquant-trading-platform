from __future__ import annotations

import argparse
from datetime import datetime
from typing import Any

from app.services.strategy_improvement.coverage import daily_coverage, latest_daily_trade_date, minute_coverage
from app.services.strategy_improvement.constraint_policy import constraint_policy_audit
from app.services.strategy_improvement.gates import build_gates
from app.services.strategy_improvement.governance import strategy_governance, strategy_inventory
from app.services.low_buy.main_force_model_shadow import summarize_main_force_shadow
from app.services.strategy_improvement.model_shadow import exit_model_shadow_status
from app.services.strategy_improvement.plans import data_backfill_plan, invariants, next_actions
from app.services.strategy_improvement.quality import data_quality_checks
from app.services.strategy_improvement.temporal_guard import temporal_guard_checks
from app.services.strategy_improvement.types import MIN_DAILY_COVERAGE_PCT, MIN_ETF_MINUTE_COVERAGE_PCT, MIN_STOCK_SYMBOLS, MIN_WF_TRADE_DAYS
from app.services.strategy_improvement.walkforward import controlled_parameter_policy, walk_forward_readiness


def build_closed_loop_report(db, *, args: argparse.Namespace, existing_report: dict[str, Any]) -> dict[str, Any]:
    requested_end = args.end or latest_daily_trade_date(db)
    daily = daily_coverage(db, start=args.start, end=requested_end, min_stock_symbols=args.min_stock_symbols)
    minute = minute_coverage(db, start=args.start, end=requested_end)
    quality = data_quality_checks(db, start=args.start, end=requested_end, daily=daily, minute=minute)
    strategies = strategy_governance(existing_report)
    constraints = constraint_policy_audit(strategies)
    walk_forward = walk_forward_readiness(
        daily=daily,
        strategies=strategies,
        min_trade_days=args.min_wf_trade_days,
        min_daily_coverage_pct=args.min_daily_coverage_pct,
    )
    model_shadow = exit_model_shadow_status(db)
    main_force_shadow = summarize_main_force_shadow(db)
    temporal_guard = temporal_guard_checks(db, walk_forward=walk_forward)
    gates = build_gates(
        daily=daily,
        minute=minute,
        quality=quality,
        strategies=strategies,
        constraints=constraints,
        walk_forward=walk_forward,
        model_shadow=model_shadow,
        temporal_guard=temporal_guard,
        min_daily_coverage_pct=args.min_daily_coverage_pct,
        min_stock_symbols=args.min_stock_symbols,
        min_etf_minute_coverage_pct=args.min_etf_minute_coverage_pct,
    )
    formal_allowed = all(item.status == "pass" for item in gates if item.severity == "blocking")
    return {
        "title": "策略胜率/盈利率提升闭环报告",
        "version": "strategy-improvement-closed-loop-v1",
        "summary": _summary(args=args, requested_end=requested_end, formal_allowed=formal_allowed, walk_forward=walk_forward),
        "data_coverage": daily,
        "minute_coverage": minute,
        "data_quality": quality,
        "strategy_inventory": strategy_inventory(existing_report, args.existing_backtest),
        "strategy_governance": strategies,
        "constraint_policy": constraints,
        "walk_forward": walk_forward,
        "auxiliary_model_shadow": model_shadow,
        "main_force_model_shadow": main_force_shadow,
        "temporal_guard": temporal_guard,
        "gates": [item.to_dict() for item in gates],
        "data_backfill_plan": data_backfill_plan(args=args, daily=daily, minute=minute),
        "controlled_parameter_policy": controlled_parameter_policy(),
        "next_actions": next_actions(
            gates=gates,
            walk_forward=walk_forward,
            model_shadow=model_shadow,
            main_force_shadow=main_force_shadow,
        ),
        "invariants": invariants(),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = _summary_lines(report)
    lines.extend(_coverage_lines(report))
    lines.extend(_gate_lines(report))
    lines.extend(_strategy_lines(report))
    lines.extend(_constraint_lines(report))
    lines.extend(_walkforward_lines(report))
    lines.extend(_temporal_guard_lines(report))
    lines.extend(_shadow_lines(report))
    lines.extend(_main_force_shadow_lines(report))
    lines.extend(_plan_lines(report))
    return "\n".join(lines) + "\n"


def _summary(args: argparse.Namespace, *, requested_end: str, formal_allowed: bool, walk_forward: dict[str, Any]) -> dict[str, Any]:
    allowed_wf = formal_allowed and walk_forward["status"] == "ready"
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "requested_window": {"start": args.start, "end": requested_end},
        "overall_status": "ready_for_formal_wf" if allowed_wf else "blocked_or_research_only",
        "formal_backtest_allowed": formal_allowed,
        "walk_forward_allowed": allowed_wf,
        "production_parameter_change_allowed": False,
        "reason": "" if formal_allowed else "两年数据覆盖、ETF 分钟线或质量门禁未达标，只允许研究/观察，不允许参数晋级。",
    }


def _summary_lines(report: dict[str, Any]) -> list[str]:
    summary = report["summary"]
    lines = [
        f"# {report['title']}",
        "",
        f"- 生成时间：{summary['generated_at']}",
        f"- 请求窗口：{summary['requested_window']['start']} 至 {summary['requested_window']['end']}",
        f"- 总体状态：{summary['overall_status']}",
        f"- 允许正式回测：{'是' if summary['formal_backtest_allowed'] else '否'}",
        f"- 允许 Walk-forward 晋级：{'是' if summary['walk_forward_allowed'] else '否'}",
        f"- 生产参数自动变更：{'允许' if summary['production_parameter_change_allowed'] else '禁止'}",
    ]
    if summary["reason"]:
        lines.append(f"- 原因：{summary['reason']}")
    return lines


def _coverage_lines(report: dict[str, Any]) -> list[str]:
    daily = report["data_coverage"]
    minute = report["minute_coverage"]
    lines = ["", "## 数据覆盖"]
    lines.append(f"- 日线状态：{daily['status']}，覆盖率 {daily['coverage_pct']}%，实际 {daily['actual_start']} 至 {daily['actual_end']}，股票数 {daily['symbol_count']}。")
    lines.append(f"- 完整交易日：{daily['complete_trade_day_count']} / {daily['trade_day_count']}。")
    if daily.get("first_missing_calendar_range"):
        lines.append(f"- 缺失区间：{daily['first_missing_calendar_range']}")
    if daily.get("missing_detail_sample"):
        first_gap = daily["missing_detail_sample"][0]
        lines.append(
            f"- 日线缺口样本：{first_gap['trade_date']} 仅 {first_gap['symbol_count']} / {first_gap['threshold']} 个股票达标，"
            f"估算缺 {first_gap['missing_symbol_estimate']} 个标的字段。"
        )
    lines.append(
        f"- 分钟线状态：{minute['status']}（原始数据状态 {minute.get('raw_data_status', minute['status'])}），窗口内分钟线 {minute.get('window_bar_count', 0)}，"
        f"库内总分钟线 {minute['bar_count']}，任意分钟线 ETF {minute['eligible_etf_with_minutes']} / {minute['eligible_etf_count']} "
        f"({minute.get('eligible_etf_any_minute_coverage_pct', 0.0)}%)，验收达标 ETF {minute.get('eligible_etf_with_sufficient_window_minutes', 0)} / "
        f"{minute['eligible_etf_count']} ({minute['eligible_etf_minute_coverage_pct']}%)。"
    )
    if minute.get("blocked_reason"):
        lines.append(f"- ETF 分钟线阻断原因：{minute['blocked_reason']}。")
    if minute.get("expected_trade_day_count"):
        lines.append(f"- ETF 分钟线验收交易日：{minute['expected_trade_day_count']} 个；近端短窗口分钟线不计作 24 个月验收通过。")
    if minute.get("out_of_window_bar_count"):
        lines.append(f"- 窗口外分钟线：{minute['out_of_window_bar_count']} 条，仅作为近端补数探针，不计入 24 个月验收。")
    if minute.get("missing_etf_symbols"):
        missing = ", ".join(item["symbol"] for item in minute["missing_etf_symbols"][:8])
        lines.append(f"- ETF 分钟线缺口样本：{missing}")
    lines.extend(_minute_provider_diagnostic_lines(minute))
    lines.extend(_quality_lines(report))
    return lines


def _minute_provider_diagnostic_lines(minute: dict[str, Any]) -> list[str]:
    diagnostics = minute.get("provider_diagnostics") or {}
    if not diagnostics or diagnostics.get("status") == "not_found":
        return []
    totals = diagnostics.get("totals") or {}
    lines = [
        f"- ETF 分钟线补数诊断：{diagnostics.get('report_path', '')}，状态 {diagnostics.get('status', 'unknown')}，"
        f"写入效果 {diagnostics.get('write_effect', '')}，totals ok={totals.get('ok', 0)} empty={totals.get('empty', 0)} error={totals.get('error', 0)}。"
    ]
    errors = diagnostics.get("provider_errors_sample") or []
    if errors:
        sample = "; ".join(
            f"{item.get('symbol', '')} {item.get('source', '')}: {item.get('message', '')}"
            for item in errors[:4]
        )
        lines.append(f"- Provider 失败样本：{sample}")
    if diagnostics.get("fake_data_policy"):
        lines.append(f"- 分钟线造数策略：{diagnostics['fake_data_policy']}。")
    return lines


def _quality_lines(report: dict[str, Any]) -> list[str]:
    quality = report["data_quality"]
    metadata = quality.get("metadata_coverage", {})
    lines = ["", "## 数据质量与元数据门禁"]
    lines.append(
        f"- OHLC 质量：{quality['status']}，重复 K 线 {quality['duplicate_daily_symbol_date_count']}，"
        f"非法 OHLC {quality['invalid_daily_ohlc_count']}，负成交 {quality['negative_volume_or_amount_count']}。"
    )
    if quality.get("lineage_field_gaps"):
        lines.append(f"- Lineage 字段缺口：{', '.join(quality['lineage_field_gaps'][:12])}")
    lines.append(f"- 交易元数据状态：{metadata.get('status', 'unknown')}，阻断缺口 {metadata.get('blocking_gap_count', 0)} 个。")
    if metadata.get("blocking_gaps"):
        lines.append(f"- 元数据缺口样本：{', '.join(metadata['blocking_gaps'][:12])}")
    for check in metadata.get("schema_checks", [])[:6]:
        if check.get("status") != "pass":
            lines.append(f"- {check['key']}：{check['reason']} 缺 {', '.join(check.get('missing', [])[:6])}")
    for check in metadata.get("data_checks", []):
        if check.get("status") != "pass":
            lines.append(f"- {check['key']}：{check['reason']} 证据 {check.get('evidence', {})}")
    return lines


def _gate_lines(report: dict[str, Any]) -> list[str]:
    lines = ["", "## 门禁", "| 门禁 | 状态 | 严重级别 | 说明 |", "|---|---|---|---|"]
    for gate in report["gates"]:
        lines.append(f"| {gate['key']} | {gate['status']} | {gate['severity']} | {gate['message']} |")
    return lines


def _strategy_lines(report: dict[str, Any]) -> list[str]:
    lines = ["", "## 策略治理", "| 策略 | 状态 | 动作 | 样本/成交 | 胜率 | PF | 平均单笔 | 最大回撤 | 止损率 |"]
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---:|")
    for item in report["strategy_governance"]["ranking"]:
        lines.append(
            "| {strategy_title} | {governance_state} | {recommended_action} | {sample_count}/{filled_count} | {win_rate_pct:.2f}% | {profit_factor:.2f} | {avg_trade_return_pct:.3f}% | {max_drawdown_pct:.2f}% | {stop_loss_rate_pct:.2f}% |".format(**item)
        )
    return lines


def _constraint_lines(report: dict[str, Any]) -> list[str]:
    policy = report["constraint_policy"]
    lines = [
        "",
        "## 约束增强审计",
        f"- 状态：{policy['status']}，问题数 {policy['issue_count']}。",
        f"- 生产影响：{policy['production_effect']}。",
        f"- 基础必需约束：{', '.join(policy['required_base_constraints'])}",
        f"- 高风险必需约束：{', '.join(policy['required_risk_constraints'])}",
    ]
    lines.extend(f"- {item}" for item in policy["notes"])
    if policy.get("issues"):
        lines.append("- 问题样本：")
        for item in policy["issues"][:8]:
            lines.append(f"  - {item['strategy_key']} {item['key']}: {', '.join(item.get('values', []))}")
    return lines


def _walkforward_lines(report: dict[str, Any]) -> list[str]:
    wf = report["walk_forward"]
    lines = [
        "",
        "## Walk-forward",
        f"- 状态：{wf['status']}",
        f"- 推荐切分：{wf['recommended_scheme']}",
        f"- 时间序列切分：{wf['time_series_split']}；随机切分：{'允许' if wf.get('random_split_allowed') else '禁止'}。",
        f"- 窗口数：{wf.get('window_count', 0)}，滚动步长：{wf.get('rolling_step', '')}。",
        f"- 候选策略数：{wf['candidate_strategy_count']}",
        f"- 阻断原因：{', '.join(wf['blocked_reasons']) if wf['blocked_reasons'] else '无'}",
    ]
    if wf.get("windows"):
        lines.extend(["", "| 窗口 | 训练 | 验证 | 样本外 | 交易日 |", "|---:|---|---|---|---:|"])
        for window in wf["windows"][:8]:
            lines.append(
                f"| {window['window_id']} | {window['train_start']} 至 {window['train_end']} | "
                f"{window['validation_start']} 至 {window['validation_end']} | {window['oos_start']} 至 {window['oos_end']} | "
                f"{window['train_trade_days']}/{window['validation_trade_days']}/{window['oos_trade_days']} |"
            )
    if wf.get("controlled_parameter_grid"):
        lines.extend(["", "- 受控参数网格："])
        for item in wf["controlled_parameter_grid"]:
            lines.append(f"  - {item['name']}: {', '.join(str(value) for value in item['values'])}")
    if wf.get("stability_checks"):
        lines.extend(["", "- 稳定性与过拟合检查："])
        for item in wf["stability_checks"]:
            lines.append(f"  - {item['key']}：{item['description']}")
    return lines


def _shadow_lines(report: dict[str, Any]) -> list[str]:
    shadow = report["auxiliary_model_shadow"]
    diff = shadow.get("action_diff", {})
    outcome = shadow.get("outcome_summary", {})
    lines = [
        "",
        "## 退出模型 Shadow",
        f"- 状态：{shadow['status']}，记录 {shadow['record_count']}，已结算 {shadow['settled_count']}。",
        f"- 生产影响：{shadow['production_effect']}；硬止损可被覆盖：{'是' if shadow['hard_stop_override_allowed'] else '否'}。",
        f"- Shadow-only：{'是' if shadow.get('shadow_only') else '否'}；可晋级：{'是' if shadow.get('promotion_ready') else '否'}。",
        f"- 动作差异：一致 {diff.get('same_as_rule', 0)}，更激进 {diff.get('more_aggressive_than_rule', 0)}，更保守 {diff.get('less_aggressive_than_rule', 0)}，fallback {diff.get('fallback', 0)}，硬止损覆盖风险 {diff.get('hard_stop_override_risk_count', 0)}。",
        f"- 后验摘要：已标注 {outcome.get('settled_or_labeled_count', 0)}，5日均收益 {outcome.get('avg_return_5d_pct', 0.0)}%，5日平均最大不利 {outcome.get('avg_max_adverse_5d_pct', 0.0)}%，卖飞率 {outcome.get('sell_flying_rate_pct', 0.0)}%。",
    ]
    if shadow.get("promotion_blockers"):
        lines.append(f"- 晋级阻断：{', '.join(shadow['promotion_blockers'])}")
    return lines


def _main_force_shadow_lines(report: dict[str, Any]) -> list[str]:
    shadow = report.get("main_force_model_shadow") or {}
    lines = [
        "",
        "## 主力模型 Shadow",
        f"- 状态：{shadow.get('status', 'unknown')}，记录 {shadow.get('record_count', 0)}，已结算 {shadow.get('settled_count', 0)}。",
        f"- 胜率：{shadow.get('success_rate_pct', 0.0)}%，PF {shadow.get('profit_factor', 0.0)}，20日均收益 {shadow.get('avg_return_20d_pct', 0.0)}%。",
        f"- 生产影响：{shadow.get('production_effect', 'readonly_shadow')}；Shadow-only：{'是' if shadow.get('shadow_only', True) else '否'}；可晋级：{'是' if shadow.get('promotion_ready') else '否'}。",
    ]
    if shadow.get("promotion_blockers"):
        lines.append(f"- 晋级阻断：{', '.join(shadow['promotion_blockers'])}")
    return lines


def _temporal_guard_lines(report: dict[str, Any]) -> list[str]:
    guard = report["temporal_guard"]
    lines = [
        "",
        "## 防未来函数门禁",
        f"- 状态：{guard['status']}，问题数 {guard['issue_count']}。",
        f"- 检查项：{', '.join(guard['checks'])}",
        f"- 禁止特征关键词：{', '.join(guard['forbidden_feature_keywords'])}",
    ]
    lines.extend(f"- {item}" for item in guard["notes"])
    if guard.get("issues"):
        lines.append("- 问题样本：")
        for item in guard["issues"][:8]:
            lines.append(f"  - {item['key']} {item}")
    return lines


def _plan_lines(report: dict[str, Any]) -> list[str]:
    lines = ["", "## 数据补齐计划"]
    for command in report["data_backfill_plan"]["commands_or_tasks"]:
        lines.append(f"- `{command}`" if command.startswith("DATABASE_URL=") else f"- {command}")
    lines.extend(["", "## 不变量"])
    for item in report["invariants"]:
        lines.append(f"- {item}")
    lines.extend(["", "## 下一步"])
    for item in report["next_actions"]:
        lines.append(f"- {item}")
    return lines


def default_args_namespace(**overrides: Any) -> argparse.Namespace:
    values = {
        "start": "2024-05-28",
        "end": "",
        "existing_backtest": "docs/reports/strategy-24m-backtest-2026-05-28.json",
        "min_daily_coverage_pct": MIN_DAILY_COVERAGE_PCT,
        "min_stock_symbols": MIN_STOCK_SYMBOLS,
        "min_etf_minute_coverage_pct": MIN_ETF_MINUTE_COVERAGE_PCT,
        "min_wf_trade_days": MIN_WF_TRADE_DAYS,
    }
    values.update(overrides)
    return argparse.Namespace(**values)
